import sys
import re
from textx import metamodel_from_file

class HardwareMemoryPool:
    def __init__(self, size=10240):
        self.pool = bytearray(size)
        self.allocations = {}
        self.free_blocks = {}
        self.offset = 0

    def allocate(self, name, voltage_size, is_signed, type_tag):
        if name in self.allocations:
            raise Exception(f"Short Circuit! Source '{name}' is already physically allocated.")

        if voltage_size <= 0:
            raise Exception(f"Hardware failure: invalid voltage width {voltage_size}v for '{name}'.")

        # Physical allocation is byte addressed; logical limits still enforced by exact bit width.
        byte_size = (voltage_size + 7) // 8
            
        addr = -1
        for free_addr, free_size in sorted(self.free_blocks.items()):
            if free_size >= byte_size:
                addr = free_addr
                remaining = free_size - byte_size
                del self.free_blocks[free_addr]
                if remaining > 0:
                    self.free_blocks[free_addr + byte_size] = remaining
                break
                
        if addr == -1:
            if self.offset + byte_size > len(self.pool):
                raise Exception(f"Out of Memory! Insufficient hardware space for '{name}' ({voltage_size}v).")
            addr = self.offset
            self.offset += byte_size
            
        self.allocations[name] = {'addr': addr, 'bytes': byte_size, 'v_size': voltage_size, 'is_signed': is_signed, 'type': type_tag}
        return name

    def _bounds_for(self, alloc):
        bit_width = alloc['v_size']
        if alloc['is_signed']:
            low = -(1 << (bit_width - 1))
            high = (1 << (bit_width - 1)) - 1
        else:
            low = 0
            high = (1 << bit_width) - 1
        return low, high

    def read_int(self, name):
        alloc = self.allocations.get(name)
        if not alloc:
            raise Exception(f"Segmentation Fault! Attempted to read uninitialized memory: {name}")

        addr = alloc['addr']
        raw = self.pool[addr:addr+alloc['bytes']]
        return int.from_bytes(raw, byteorder='little', signed=alloc['is_signed'])

    def write_int(self, name, value):
        alloc = self.allocations.get(name)
        if not alloc:
            raise Exception(f"Segmentation Fault! Attempted to write to unallocated memory: {name}")

        low, high = self._bounds_for(alloc)
        if value < low or value > high:
            sign_text = "signed" if alloc['is_signed'] else "unsigned"
            raise Exception(
                f"Overload! Value {value} physically exceeds the {alloc['v_size']}v {sign_text} boundaries of '{name}' "
                f"(allowed range: {low}..{high})."
            )

        addr = alloc['addr']

        try:
            packed = int(value).to_bytes(alloc['bytes'], byteorder='little', signed=alloc['is_signed'])
            self.pool[addr:addr+alloc['bytes']] = packed
        except OverflowError:
            sign_text = "signed" if alloc['is_signed'] else "unsigned"
            raise Exception(f"Overload! Value {value} physically exceeds the {alloc['v_size']}v {sign_text} boundaries of '{name}'.")

    def read_string(self, name):
        alloc = self.allocations.get(name)
        addr = alloc['addr']
        size = alloc['bytes']
        raw_bytes = self.pool[addr:addr+size]
        end = raw_bytes.find(b'\x00')
        if end != -1:
            raw_bytes = raw_bytes[:end]
        return raw_bytes.decode('utf-8')

    def write_string(self, name, text):
        alloc = self.allocations.get(name)
        addr = alloc['addr']
        size = alloc['bytes']
        encoded = text.encode('utf-8')
        
        if len(encoded) > size:
            raise Exception(f"Overload! String '{text}' ({len(encoded)} bytes) exceeds '{name}' capacity of {size} bytes.")
            
        for i in range(size):
            self.pool[addr + i] = 0
        self.pool[addr:addr+len(encoded)] = encoded

    def destroy(self, name):
        if name in self.allocations:
            alloc = self.allocations[name]
            addr = alloc['addr']
            size = alloc['bytes']
            
            for i in range(addr, addr + size):
                self.pool[i] = 0
                
            self.free_blocks[addr] = size
            del self.allocations[name]


class VoltInterpreter:
    def __init__(self):
        self.mem = HardwareMemoryPool()

    def perform_static_analysis(self, statements):
        def analyze_trace(trace_stmt, allocated):
            allocated = set(allocated)
            current_ref = trace_stmt.start.name if trace_stmt.start.__class__.__name__ == "SourceRef" else None
            pending_declaration = False

            if current_ref is not None and current_ref not in allocated:
                raise Exception(f"Compile Error: SourceRef '{current_ref}' is not allocated before use.")

            for pipe in trace_stmt.pipes:
                if isinstance(pipe, str):
                    if pipe == "_|_":
                        if current_ref is not None:
                            if current_ref not in allocated:
                                raise Exception(f"Compile Error: Ground attempted on non-allocated source '{current_ref}'.")
                            allocated.remove(current_ref)
                        current_ref = None
                    elif pipe == "(O)":
                        pass
                    else:
                        raise Exception(f"Compile Error: Unknown inline pipe '{pipe}'.")
                    continue

                pipe_cls = pipe.__class__.__name__
                if pipe_cls == "VoltageSource":
                    if pending_declaration:
                        raise Exception("Compile Error: Consecutive voltage declarations without a storage target.")
                    pending_declaration = True
                elif pipe_cls == "CapacitorStore":
                    if pending_declaration:
                        if pipe.name in allocated:
                            raise Exception(f"Compile Error: Source '{pipe.name}' declared multiple times without grounding.")
                        allocated.add(pipe.name)
                    current_ref = pipe.name
                    pending_declaration = False
                elif pipe_cls == "SourceRef":
                    if pipe.name not in allocated:
                        raise Exception(f"Compile Error: SourceRef '{pipe.name}' is not allocated before use.")
                    current_ref = pipe.name
                elif pipe_cls in ("MathOp", "LogicOp"):
                    pass
                else:
                    raise Exception(f"Compile Error: Unknown pipe node '{pipe_cls}'.")

            if pending_declaration:
                raise Exception("Compile Error: Voltage source tag must be followed by a capacitor store.")
            return allocated

        def analyze_block(stmts, in_states):
            states = {frozenset(s) for s in in_states}
            for stmt in stmts:
                cls_name = stmt.__class__.__name__
                new_states = set()

                if cls_name == "Trace":
                    for state in states:
                        out_state = analyze_trace(stmt, set(state))
                        new_states.add(frozenset(out_state))

                elif cls_name == "Loop":
                    iterations = stmt.count.value
                    if iterations < 0:
                        raise Exception("Compile Error: Loop count cannot be negative.")
                    new_states = set(states)
                    for _ in range(iterations):
                        new_states = analyze_block(stmt.statements, new_states)

                elif cls_name == "Branch":
                    high_states = analyze_block(stmt.high_statements, states)
                    if stmt.low_statements:
                        low_states = analyze_block(stmt.low_statements, states)
                    else:
                        low_states = set(states)
                    new_states = high_states | low_states

                else:
                    raise Exception(f"Compile Error: Unknown statement type '{cls_name}'.")

                states = new_states

            return states

        out_states = analyze_block(statements, {frozenset()})
        leaking_states = [sorted(list(s)) for s in out_states if s]
        if leaking_states:
            flattened = sorted({name for state in leaking_states for name in state})
            raise Exception(
                "Compile Error: The following sources may remain allocated at program termination on at least one path: "
                + ", ".join(flattened)
            )

    def evaluate_expression(self, expr):
        cls_name = expr.__class__.__name__
        if cls_name == "StringLit":
            return expr.value, "string"
        elif cls_name == "IntLit":
            return expr.value, "int"
        elif cls_name == "BoolLit":
            return expr.value, "bool"
        elif cls_name == "SourceRef":
            alloc = self.mem.allocations.get(expr.name)
            if not alloc:
                raise Exception(f"Short Circuit! Uninitialized or grounded memory: {expr.name}")
            
            c_type = alloc['type']
            if c_type == "int":
                return self.mem.read_int(expr.name), "int"
            elif c_type == "string":
                return self.mem.read_string(expr.name), "string"
            elif c_type == "bool":
                val = self.mem.read_int(expr.name)
                return ("[^]" if val == 1 else "[v]"), "bool"
        return None, None

    def execute_statement(self, stmt):
        cls_name = stmt.__class__.__name__

        if cls_name == "Trace":
            current_val, current_type = self.evaluate_expression(stmt.start)
            current_ref = None
            pending_v_spec = None
            
            if stmt.start.__class__.__name__ == "SourceRef":
                current_ref = stmt.start.name

            if not stmt.pipes:
                raise Exception("Open Trace!")

            last_pipe = stmt.pipes[-1]
            if (isinstance(last_pipe, str) and last_pipe != "_|_") or (
                not isinstance(last_pipe, str) and last_pipe.__class__.__name__ != "CapacitorStore"
            ):
                 raise Exception("Open Trace! Traces must terminate at || or _|_.")

            for pipe in stmt.pipes:
                if isinstance(pipe, str):
                    if pipe == "_|_":
                        if current_ref is not None:
                            self.mem.destroy(current_ref)
                        current_ref = None
                        current_val = None
                        continue
                    if pipe == "(O)":
                        print(current_val)
                        continue
                    raise Exception(f"Unknown inline pipe: {pipe}")

                p_cls = pipe.__class__.__name__

                if p_cls == "VoltageSource":
                    tag = pipe.tag
                    is_signed = tag.startswith('[-')
                    v_size = int(re.search(r'\d+', tag).group())
                    pending_v_spec = (v_size, is_signed)

                elif p_cls == "CapacitorStore":
                    if pipe.name not in self.mem.allocations:
                        if pending_v_spec is None:
                            raise Exception(
                                f"Compile/Runtime Error: '{pipe.name}' must be declared with a voltage source tag before first store."
                            )
                        v_size, is_signed = pending_v_spec
                        self.mem.allocate(pipe.name, v_size, is_signed, current_type)
                    elif pending_v_spec is not None:
                        raise Exception(
                            f"Compile/Runtime Error: '{pipe.name}' is already declared. Remove redundant voltage declaration."
                        )
                    
                    self.mem.allocations[pipe.name]['type'] = current_type
                    if current_type == "int":
                        self.mem.write_int(pipe.name, current_val)
                    elif current_type == "string":
                        self.mem.write_string(pipe.name, current_val)
                    elif current_type == "bool":
                        self.mem.write_int(pipe.name, 1 if current_val in ["[^]", True] else 0)
                    
                    current_ref = pipe.name
                    pending_v_spec = None

                elif p_cls == "SourceRef":
                    current_val, current_type = self.evaluate_expression(pipe)

                elif p_cls == "MathOp":
                    op_val, op_type = self.evaluate_expression(pipe.val)
                    if current_type != "int" or op_type != "int":
                        raise Exception("Math operations require voltage integers.")
                    
                    if pipe.op == "(+)":
                        current_val += op_val
                    elif pipe.op == "(-)":
                        current_val -= op_val
                    elif pipe.op == "(%)":
                        if op_val == 0:
                            raise Exception("Math fault: modulo by zero is not physically valid.")
                        current_val %= op_val

                elif p_cls == "LogicOp":
                    op_val, op_type = self.evaluate_expression(pipe.val)
                    
                    if pipe.op == "(=)":
                        if current_type != op_type:
                            raise Exception("Logic operations require compatible operand types.")
                        current_val = "[^]" if current_val == op_val else "[v]"
                    elif pipe.op == "(>)":
                        if current_type != "int" or op_type != "int":
                            raise Exception("Logic operations (>) require voltage integers.")
                        current_val = "[^]" if current_val > op_val else "[v]"
                    elif pipe.op == "(<)":
                        if current_type != "int" or op_type != "int":
                            raise Exception("Logic operations (<) require voltage integers.")
                        current_val = "[^]" if current_val < op_val else "[v]"
                        
                    current_type = "bool"
                else:
                    raise Exception(f"Unknown pipe node: {p_cls}")

        elif cls_name == "Loop":
            iterations = stmt.count.value
            for _ in range(iterations):
                for s in stmt.statements:
                    self.execute_statement(s)

        elif cls_name == "Branch":
            cond_val, cond_type = self.evaluate_expression(stmt.condition)
            if cond_type != "bool":
                raise Exception("Branch condition must evaluate to a boolean signal ([^] or [v]).")
            if cond_val == "[^]" or cond_val is True:
                for s in stmt.high_statements:
                    self.execute_statement(s)
            elif stmt.low_statements:
                for s in stmt.low_statements:
                    self.execute_statement(s)

    def run(self, filepath):
        try:
            volt_mm = metamodel_from_file("volt.tx")
            model = volt_mm.model_from_file(filepath)
            
            self.perform_static_analysis(model.statements)
            
            for stmt in model.statements:
                self.execute_statement(stmt)
                
        except Exception as e:
            print(f"Compilation/Execution Error:\n{e}")
        finally:
            # Hard lifecycle guarantee: no allocated source survives process termination, even on faults.
            for name in list(self.mem.allocations.keys()):
                self.mem.destroy(name)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python interpreter.py <file.volt>")
        sys.exit(1)

    interpreter = VoltInterpreter()
    interpreter.run(sys.argv[1])
