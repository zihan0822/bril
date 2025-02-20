import json
import sys

from cfg import block_map, successors, add_terminators, add_entry, reassemble
from form_blocks import form_blocks


def get_types(func):
    """Find the types of all variables defined in a function.

    According to the Bril spec, well-formed programs must use only a single
    type for every variable within a given function. So we just take the
    type of the first assignment we see to each variable in the function.
    """
    types = {arg["name"]: arg["type"] for arg in func.get("args", [])}
    for instr in func["instrs"]:
        if "dest" in instr:
            types[instr["dest"]] = instr["type"]
    return types


def local_name(block_name, var_name, index=0):
    if index:
        return f"{var_name}_{block_name}_{index}"
    else:
        return f"{var_name}_{block_name}"


def block_to_ssa(block, block_name, succ_names, var_types):
    # Replace all variables with local names.
    version = {v: 0 for v in var_types}
    for instr in block:
        if "args" in instr:
            instr["args"] = [
                local_name(block_name, a, version[a]) for a in instr["args"]
            ]
        if "dest" in instr:
            version[instr["dest"]] += 1
            instr["dest"] = local_name(
                block_name, instr["dest"], version[instr["dest"]]
            )

    # Add phis to the top.
    for var, type in var_types.items():
        phi = {"op": "phi", "dest": local_name(block_name, var), "type": type}
        block.insert(0, phi)

    # Add upsilons to the bottom, before the terminator.
    for succ in succ_names:
        for var in var_types:
            upsilon = {
                "op": "upsilon",
                "args": [
                    local_name(succ, var),
                    local_name(block_name, var, version[var]),
                ],
            }
            block.insert(-1, upsilon)


def func_to_ssa(func):
    # Construct a well-behaved CFG.
    blocks = block_map(form_blocks(func["instrs"]))
    add_entry(blocks)
    add_terminators(blocks)
    succ = {name: successors(block[-1]) for name, block in blocks.items()}

    # Rename all variables within the block and insert upsilon/phi.
    var_types = get_types(func)
    for name, block in blocks.items():
        block_to_ssa(block, name, succ[name], var_types)

    # Reassemble the CFG for output.
    func["instrs"] = reassemble(blocks)

    # "Bootstrap" with upsilons for the entry.
    entry = next(iter(blocks.keys()))
    arg_names = [a["name"] for a in func.get("args", [])]
    prelude = []
    for var in var_types:
        src = var if var in arg_names else "undef"
        upsilon = {
            "op": "upsilon",
            "args": [local_name(var, entry), src],
        }
        prelude.append(upsilon)
    func["instrs"][:0] = prelude


def to_ssa(bril):
    for func in bril["functions"]:
        func_to_ssa(func)
    return bril


if __name__ == "__main__":
    print(json.dumps(to_ssa(json.load(sys.stdin)), indent=2, sort_keys=True))
