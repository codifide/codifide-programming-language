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

fn parse_source(path: &str) -> codifide_canonical::ast::Module {
    let source = read_source(path);
    // Derive module name from filename stem.
    let stem = std::path::Path::new(path)
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("main");
    match codifide_interpreter::parse(&source, stem) {
        Ok(m) => m,
        Err(e) => {
            eprintln!("parse error: {}", e);
            process::exit(1);
        }
    }
}

fn cmd_parse(args: &[String]) {
    let path = &args[2];
    let module = parse_source(path);
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

    // Parse optional flags: --entry <name> and --args <json_array>
    let mut entry = "main".to_string();
    let mut call_args: Vec<codifide_interpreter::Value> = vec![];
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
            _ => {}
        }
        i += 1;
    }

    let module = parse_source(path);

    match codifide_interpreter::run(&module, &entry, call_args) {
        Ok(result) => {
            println!("{}", result.to_json());
        }
        Err(e) => {
            eprintln!("runtime error: {}", e);
            process::exit(1);
        }
    }
}
