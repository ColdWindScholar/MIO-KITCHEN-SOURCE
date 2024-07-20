# Te2Cil By LazyBones
def te_to_cil(te_rules):
    cil_rules = []
    skipped_lines = []
    for i, line in enumerate(te_rules.strip().split('\n'), 1):
        if not line.strip():
            continue
        try:
            parts = line.split()
            if len(parts) < 4:
                raise ValueError("Unexpected rule format: less than 4 parts")

            source = parts[1]
            target_class = parts[2].split(':')
            if len(target_class) != 2:
                raise ValueError(f"Unexpected target:class format: {parts[2]}")

            target = target_class[0]
            clazz = target_class[1]

            # Handling permissions with and without braces
            if parts[3] == '{':
                permissions = parts[4:-1]  # Exclude the closing brace
            else:
                permissions = [parts[3].strip(';')]

            if not permissions:
                raise ValueError(f"No permissions found in: {parts[3:]}")

            cil_rule = f"(allow {source} {target} ({clazz} ({' '.join(f'({perm})' for perm in permissions)})))"
            cil_rules.append(cil_rule)
        except Exception as e:
            skipped_lines.append((i, line, str(e)))
            print(f"跳过了 line {i}: {line}, Error: {str(e)}")

    return '\n'.join(cil_rules), skipped_lines





def main(input_, output):
    with open(input_, 'r') as file:
        te_rules = file.read()
    cil_content, skipped_lines = te_to_cil(te_rules)
    with open(output, 'w') as cil_file:
        cil_file.write(cil_content)
        print(f"转换完成")

    for line_info in skipped_lines:
        print(f"跳过了 invalid line {line_info[0]}: {line_info[1]}, Error: {line_info[2]}")
