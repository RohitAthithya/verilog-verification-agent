def analyze_results(sim_results: dict) -> dict:
    compiled_ok = []
    compile_failed = []
    passed = []
    failed = []

    for rtl_name, result in sim_results.items():
        if not result["compiled"]:
            compile_failed.append(rtl_name)
            continue

        compiled_ok.append(rtl_name)

        if result["passed"]:
            passed.append(rtl_name)
        else:
            failed.append(rtl_name)

    good_enough = len(passed) == 1 and len(failed) >= 1

    return {
        "compiled_ok": compiled_ok,
        "compile_failed": compile_failed,
        "passed": passed,
        "failed": failed,
        "good_enough": good_enough,
        "summary": (
            f"Compiled: {len(compiled_ok)}, "
            f"Compile failed: {len(compile_failed)}, "
            f"Passed: {len(passed)}, "
            f"Failed: {len(failed)}"
        ),
    }