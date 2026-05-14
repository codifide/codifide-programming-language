//! `codifide-run` — CLI binary for the Rust interpreter.
//!
//! Subcommands:
//!   run   <file.cod> [--entry <name>] [--args <json_array>]
//!         Parse and run a .cod source file; print result to stdout.
//!   parse <file.cod>
//!         Parse a .cod source file and print canonical JSON to stdout.
//!         Used by the Python conformance bridge and the Python CLI.

use std::process;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() < 3 {
        eprintln!("usage: codifide-run <run|parse> <file.cod> [options]");
        process::exit(1);
    }
    match args[1].as_str() {
        "run"   => cmd_run(&args),
        "parse" => cmd_parse(&args),
        other   => {
            eprintln!("unknown subcommand: {}", other);
            process::exit(1);
        }
    }
}

fn read_source(path: &str) -> String {
    match std::fs::read_to_string(path) {
        Ok(s) => s,
        Err(e) => {
            eprintln!("error reading {:?}: {}", path, e);
            process::exit(1);
        }
    }
}

fn parse_source(path: &str, store_root: Option<&std::path::Path>) -> codifide_canonical::ast::Module {
    let source = read_source(path);
    // Derive module name from filename stem.
    let stem = std::path::Path::new(path)
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("main");
    match codifide_interpreter::parse_with_store(&source, stem, store_root) {
        Ok(m) => m,
        Err(e) => {
            eprintln!("parse error: {}", e);
            process::exit(1);
        }
    }
}

fn cmd_parse(args: &[String]) {
    let path = &args[2];
    let module = parse_source(path, None);
    let json_val = codifide_canonical::to_canonical_json(&module);
    match serde_json::to_string(&json_val) {
        Ok(s) => println!("{}", s),
        Err(e) => {
            eprintln!("serialization error: {}", e);
            process::exit(1);
        }
    }
}

fn cmd_run(args: &[String]) {
    let path = &args[2];

    // Parse optional flags: --entry <name>, --args <json_array>, --store <path>
    let mut entry = "main".to_string();
    let mut call_args: Vec<codifide_interpreter::Value> = vec![];
    let mut store_path: Option<std::path::PathBuf> = None;
    let mut i = 3;
    while i < args.len() {
        match args[i].as_str() {
            "--entry" => {
                i += 1;
                if i < args.len() { entry = args[i].clone(); }
            }
            "--args" => {
                i += 1;
                if i < args.len() {
                    match serde_json::from_str::<serde_json::Value>(&args[i]) {
                        Ok(serde_json::Value::Array(arr)) => {
                            call_args = arr.iter().map(|v| {
                                codifide_interpreter::Value::concrete(
                                    codifide_interpreter::value::payload_from_json(v)
                                )
                            }).collect();
                        }
                        _ => {
                            eprintln!("--args must be a JSON array");
                            process::exit(1);
                        }
                    }
                }
            }
            "--store" => {
                i += 1;
                if i < args.len() {
                    store_path = Some(std::path::PathBuf::from(&args[i]));
                }
            }
            _ => {}
        }
        i += 1;
    }

    let store_ref = store_path.as_deref();
    let module = parse_source(path, store_ref);

    // Resolve imports from the store if a store path is provided.
    let resolved_imports = if let Some(store) = store_ref {
        resolve_imports_from_store(&module, store)
    } else {
        std::collections::HashMap::new()
    };

    match codifide_interpreter::run_with_imports(&module, &entry, call_args, resolved_imports) {
        Ok(result) => {
            println!("{}", result.to_json());
        }
        Err(e) => {
            eprintln!("runtime error: {}", e);
            process::exit(1);
        }
    }
}

fn resolve_imports_from_store(
    module: &codifide_canonical::ast::Module,
    store_root: &std::path::Path,
) -> std::collections::HashMap<String, codifide_canonical::ast::Definition> {
    let mut out = std::collections::HashMap::new();
    for (local_name, identity) in &module.imports {
        let digest = &identity[7..]; // strip "sha256:"
        let shard = &digest[..2];
        let rest = &digest[2..];
        let base = store_root.join("sha256").join(shard);

        let obj: Option<serde_json::Value> = {
            let json_path = base.join(format!("{}.json", rest));
            let cbor_path = base.join(format!("{}.cbor", rest));
            if json_path.exists() {
                std::fs::read(&json_path).ok()
                    .and_then(|d| serde_json::from_slice(&d).ok())
            } else if cbor_path.exists() {
                std::fs::read(&cbor_path).ok()
                    .and_then(|d| codifide_canonical::decode_canonical_cbor(&d).ok())
            } else {
                eprintln!("error: import {:?} = {} not found in store at {}",
                    local_name, identity, store_root.display());
                process::exit(1);
            }
        };

        match obj {
            Some(obj) => {
                match codifide_canonical::from_canonical_json(&obj) {
                    Ok(imported_module) => {
                        if let Some((_, defn)) = imported_module.symbols.into_iter().next() {
                            out.insert(local_name.clone(), defn);
                        } else {
                            eprintln!("error: import {:?} = {} has no symbols", local_name, identity);
                            process::exit(1);
                        }
                    }
                    Err(e) => {
                        eprintln!("error: cannot decode import {:?} = {}: {}", local_name, identity, e);
                        process::exit(1);
                    }
                }
            }
            None => {
                eprintln!("error: cannot read import {:?} = {} from store", local_name, identity);
                process::exit(1);
            }
        }
    }
    out
}
