import sys
from textx import metamodel_from_file


class VoltInterpreter:
    def __init__(self):
        self.memory = {}
        self.capacity = {}

    def evaluate_expression(self, expr):
        cls_name = expr.__class__.__name__
        if cls_name == "StringLit":
            return expr.value
        elif cls_name == "IntLit":
            return expr.value
        elif cls_name == "BoolLit":
            return True if expr.value == "HIGH" else False
        elif cls_name == "CapacitorRef":
            if expr.name not in self.memory:
                raise Exception(f"Short Circuit! Uninitialized capacitor: {expr.name}")
            return self.memory[expr.name]
        return None

    def execute_statement(self, stmt):
        cls_name = stmt.__class__.__name__

        if cls_name == "Trace":
            current_val = self.evaluate_expression(stmt.start)

            for pipe in stmt.pipes:
                p_cls = pipe.__class__.__name__

                if p_cls == "CapacitorDecl":
                    if isinstance(current_val, int) and current_val > pipe.size:
                        raise Exception(
                            f"Overload! Value {current_val}v exceeds {pipe.name} capacity of {pipe.size}v"
                        )
                    self.memory[pipe.name] = current_val
                    self.capacity[pipe.name] = pipe.size

                elif p_cls == "CapacitorRef":
                    self.memory[pipe.name] = current_val

                elif p_cls == "PrintNode":
                    print(current_val)

                elif p_cls == "MathOp":
                    operand = self.evaluate_expression(pipe.val)
                    if pipe.op == "Add":
                        current_val += operand
                    elif pipe.op == "Sub":
                        current_val -= operand
                    elif pipe.op == "Mod":
                        current_val %= operand

                elif p_cls == "LogicOp":
                    operand = self.evaluate_expression(pipe.val)
                    if pipe.op == "Eq":
                        current_val = "HIGH" if current_val == operand else "LOW"
                    elif pipe.op == "Gt":
                        current_val = "HIGH" if current_val > operand else "LOW"
                    elif pipe.op == "Lt":
                        current_val = "HIGH" if current_val < operand else "LOW"

        elif cls_name == "Loop":
            iterations = stmt.count.value
            for _ in range(iterations):
                for s in stmt.statements:
                    self.execute_statement(s)

        elif cls_name == "Branch":
            cond_val = self.evaluate_expression(stmt.condition)
            if cond_val == "HIGH" or cond_val is True:
                for s in stmt.high_statements:
                    self.execute_statement(s)
            elif stmt.low_statements:
                for s in stmt.low_statements:
                    self.execute_statement(s)

    def run(self, filepath):
        try:
            volt_mm = metamodel_from_file("volt.tx")
            model = volt_mm.model_from_file(filepath)
            for stmt in model.statements:
                self.execute_statement(stmt)
        except Exception as e:
            print(f"Compilation/Execution Error:\n{e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python interpreter.py <file.volt>")
        sys.exit(1)

    interpreter = VoltInterpreter()
    interpreter.run(sys.argv[1])
