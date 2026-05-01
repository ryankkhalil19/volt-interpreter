import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
import importlib.util


ROOT_DIR = Path(__file__).resolve().parents[1]
INTERPRETER_DIR = ROOT_DIR / "interpreter"
SAMPLE_DIR = ROOT_DIR / "sample_programs"


def load_interpreter_class():
    module_path = INTERPRETER_DIR / "interpreter.py"
    spec = importlib.util.spec_from_file_location("volt_interpreter_module", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.VoltInterpreter


class VoltEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.VoltInterpreter = load_interpreter_class()

    def run_source(self, source_code: str):
        with tempfile.NamedTemporaryFile("w", suffix=".volt", delete=False) as tmp_file:
            tmp_file.write(source_code)
            tmp_path = tmp_file.name

        prev_cwd = os.getcwd()
        os.chdir(INTERPRETER_DIR)
        try:
            interpreter = self.VoltInterpreter()
            output = io.StringIO()
            with redirect_stdout(output):
                interpreter.run(tmp_path)
            return output.getvalue(), interpreter.mem.allocations.copy()
        finally:
            os.chdir(prev_cwd)
            os.unlink(tmp_path)

    def run_sample(self, filename: str):
        prev_cwd = os.getcwd()
        os.chdir(INTERPRETER_DIR)
        try:
            interpreter = self.VoltInterpreter()
            output = io.StringIO()
            with redirect_stdout(output):
                interpreter.run(str(SAMPLE_DIR / filename))
            return output.getvalue(), interpreter.mem.allocations.copy()
        finally:
            os.chdir(prev_cwd)

    def assert_error(self, output: str, expected_substring: str):
        self.assertIn("Compilation/Execution Error:", output)
        self.assertIn(expected_substring, output)

    def assert_clean_shutdown(self, remaining_allocations):
        self.assertEqual(remaining_allocations, {})

    # --- Sample program conformance ---
    def test_sample_auth_simulation(self):
        output, remaining = self.run_sample("auth_simulation.volt")
        self.assertIn("Access Granted", output)
        self.assert_clean_shutdown(remaining)

    def test_sample_fizzbuzz(self):
        output, remaining = self.run_sample("fizzbuzz.volt")
        self.assertIn("FizzBuzz", output)
        self.assertIn("14", output)
        self.assert_clean_shutdown(remaining)

    def test_sample_signed_math(self):
        output, remaining = self.run_sample("math_ops.volt")
        self.assertIn("Signed result (8-bit):", output)
        self.assertIn("-5", output)
        self.assert_clean_shutdown(remaining)

    # --- Leak guarantees / allocation lifecycle ---
    def test_rejects_ungrounded_allocation(self):
        output, remaining = self.run_source(
            '1v ===> [+8v-] ===> || value ;'
        )
        self.assert_error(output, "may remain allocated")
        self.assertIn("value", output)
        self.assert_clean_shutdown(remaining)

    def test_rejects_path_dependent_branch_leak(self):
        output, remaining = self.run_source(
            '1v ===> [+8v-] ===> || value ;\n'
            '_/_[ [v] ] {\n'
            '  [^]: value ===> _|_ ;\n'
            '  [v]: "skip" ===> (O) ===> _|_ ;\n'
            '}\n'
        )
        self.assert_error(output, "may remain allocated")
        self.assertIn("value", output)
        self.assert_clean_shutdown(remaining)

    def test_allows_redeclaration_after_ground(self):
        output, remaining = self.run_source(
            '1v ===> [+8v-] ===> || value ;\n'
            'value ===> _|_ ;\n'
            '2v ===> [+8v-] ===> || value ;\n'
            'value ===> _|_ ;\n'
        )
        self.assertNotIn("Compilation/Execution Error:", output)
        self.assert_clean_shutdown(remaining)

    def test_rejects_duplicate_declaration_without_ground(self):
        output, remaining = self.run_source(
            '1v ===> [+8v-] ===> || value ;\n'
            '2v ===> [+8v-] ===> || value ;\n'
            'value ===> _|_ ;\n'
        )
        self.assert_error(output, "declared multiple times")
        self.assert_clean_shutdown(remaining)

    # --- Grammar / structural guarantees ---
    def test_rejects_voltage_tag_without_store_target(self):
        output, remaining = self.run_source(
            '1v ===> [+8v-] ===> _|_ ;\n'
        )
        self.assert_error(output, "Voltage source tag must be followed by a capacitor store")
        self.assert_clean_shutdown(remaining)

    def test_rejects_unterminated_trace_via_compile_leak_guard(self):
        output, remaining = self.run_source(
            '1v ===> [+8v-] ===> || value ;\n'
            'value ===> (O) ;\n'
        )
        self.assert_error(output, "may remain allocated")
        self.assert_clean_shutdown(remaining)

    def test_rejects_parse_error_for_invalid_token(self):
        output, remaining = self.run_source(
            '1v ===> [+8v-] ===> || value ;\n'
            'value ===> ??? ===> _|_ ;\n'
        )
        self.assert_error(output, "Expected")
        self.assert_clean_shutdown(remaining)

    # --- Runtime semantic guarantees ---
    def test_rejects_source_ref_after_ground(self):
        output, remaining = self.run_source(
            '1v ===> [+8v-] ===> || value ;\n'
            'value ===> _|_ ;\n'
            'value ===> (O) ===> _|_ ;\n'
        )
        self.assert_error(output, "is not allocated before use")
        self.assert_clean_shutdown(remaining)

    def test_requires_boolean_branch_condition(self):
        output, remaining = self.run_source(
            '1v ===> [+8v-] ===> || value ;\n'
            '_/_[value] {\n'
            '  [^]: "bad" ===> (O) ===> _|_ ;\n'
            '  [v]: "bad" ===> (O) ===> _|_ ;\n'
            '}\n'
            'value ===> _|_ ;\n'
        )
        self.assert_error(output, "Branch condition must evaluate to a boolean signal")
        self.assert_clean_shutdown(remaining)

    def test_rejects_modulo_by_zero(self):
        output, remaining = self.run_source(
            '2v ===> [+8v-] ===> || value ;\n'
            'value ===> (%) 0v ===> || value ;\n'
            'value ===> _|_ ;\n'
        )
        self.assert_error(output, "modulo by zero")
        self.assert_clean_shutdown(remaining)

    def test_rejects_incompatible_logic_types(self):
        output, remaining = self.run_source(
            '"x" ===> [+16v-] ===> || text_value ;\n'
            'text_value ===> (>) 1v ===> [+8v-] ===> || cmp ;\n'
            'text_value ===> _|_ ;\n'
            'cmp ===> _|_ ;\n'
        )
        self.assert_error(output, "require voltage integers")
        self.assert_clean_shutdown(remaining)

    # --- Physical memory constraints ---
    def test_unsigned_underflow_is_rejected(self):
        output, remaining = self.run_source(
            '0v ===> [+8v-] ===> || unsigned_counter ;\n'
            'unsigned_counter ===> (-) 1v ===> || unsigned_counter ;\n'
            'unsigned_counter ===> _|_ ;\n'
        )
        self.assert_error(output, "unsigned boundaries")
        self.assertIn("allowed range: 0..255", output)
        self.assert_clean_shutdown(remaining)

    def test_signed_8bit_lower_bound_is_enforced(self):
        output, remaining = self.run_source(
            '0v ===> [-8v+] ===> || signed_counter ;\n'
            'signed_counter ===> (-) 129v ===> || signed_counter ;\n'
            'signed_counter ===> _|_ ;\n'
        )
        self.assert_error(output, "signed boundaries")
        self.assertIn("allowed range: -128..127", output)
        self.assert_clean_shutdown(remaining)

    def test_non_byte_aligned_width_is_enforced(self):
        output, remaining = self.run_source(
            '255v ===> [-9v+] ===> || nine_bit_signed ;\n'
            'nine_bit_signed ===> (+) 1v ===> || nine_bit_signed ;\n'
            'nine_bit_signed ===> _|_ ;\n'
        )
        self.assert_error(output, "allowed range: -256..255")
        self.assert_clean_shutdown(remaining)

    def test_dynamic_small_width_allocation(self):
        output, remaining = self.run_source(
            '7v ===> [+3v-] ===> || tiny_unsigned ;\n'
            'tiny_unsigned ===> (O) ===> || tiny_unsigned ;\n'
            'tiny_unsigned ===> _|_ ;\n'
        )
        self.assertNotIn("Compilation/Execution Error:", output)
        self.assertIn("7", output)
        self.assert_clean_shutdown(remaining)

    # --- Fault cleanup guarantee (zero leaked allocations after failure) ---
    def test_cleanup_after_runtime_failure(self):
        output, remaining = self.run_source(
            '1v ===> [+8v-] ===> || value ;\n'
            'value ===> (%) 0v ===> || value ;\n'
            'value ===> _|_ ;\n'
        )
        self.assert_error(output, "modulo by zero")
        self.assert_clean_shutdown(remaining)


if __name__ == "__main__":
    unittest.main(verbosity=2)
