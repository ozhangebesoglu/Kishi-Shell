import os
import glob
from .state import LOCAL_VARS, ALIASES
from .lexer import QUOTE_SINGLE, QUOTE_DOUBLE, QUOTE_DOLLAR_SINGLE

class Expander:
    @staticmethod
    def expand(arg_list, globbing=True):
        """Expands globs (*, ?), variables ($VAR) and command substitutions ($(cmd) / `cmd`)"""
        import re
        import subprocess

        expanded_args = []
        for arg in arg_list:
            # Check for quote-type sentinel prefixes from the lexer
            # \x01 = single-quoted: NO expansion at all
            # \x02 = double-quoted: variable + command substitution only (no glob, no tilde)
            quote_type = None
            if arg.startswith(QUOTE_SINGLE):
                quote_type = 'single'
                arg = arg[1:]  # Strip the sentinel prefix
            elif arg.startswith(QUOTE_DOLLAR_SINGLE):
                quote_type = 'single'  # Same no-expansion behavior
                arg = arg[1:]  # Strip the sentinel prefix
            elif arg.startswith(QUOTE_DOUBLE):
                quote_type = 'double'
                arg = arg[1:]  # Strip the sentinel prefix

            # Single-quoted: emit as-is with zero expansion
            if quote_type == 'single':
                expanded_args.append(arg)
                continue

            # 1. Command Substitution — $(...) with balanced parens, and `...`
            arg = Expander._command_substitute(arg)

            # 2. Variable Expansion ($VAR or ${VAR}, unquoted and double-quoted)
            # A token that is *exactly* one variable takes the drop-if-empty path
            # (word removal); "$VAR/suffix" falls to the regex so the suffix is
            # kept. Double-quoted empty/undefined vars still yield "".
            _var_pat = r'\$\{([^}]+)\}|\$([A-Za-z0-9_?#0]+|\?)|\$\$'
            bare = re.fullmatch(_var_pat, arg)
            
            def get_raw_var_value(var_name):
                if not var_name:
                    return ""
                if var_name == '?':
                    return LOCAL_VARS.get('?', '0')
                if var_name == '$' or var_name == '$$':
                    return str(os.getpid())
                if var_name == '0':
                    return 'kishi'
                return LOCAL_VARS.get(var_name, os.environ.get(var_name, ALIASES.get(var_name, "")))

            def get_var_value(expr):
                if not expr:
                    return ""
                # 1. Length expansion: ${#VAR}
                if expr.startswith('#') and len(expr) > 1:
                    real_var = expr[1:]
                    val = get_raw_var_value(real_var)
                    return str(len(val))

                # 2. Default value: ${VAR:-default}
                if ':-' in expr:
                    var_name, default_val = expr.split(':-', 1)
                    val = get_raw_var_value(var_name)
                    if not val:
                        return default_val
                    return val

                # 3. Assign default: ${VAR:=default}
                if ':=' in expr:
                    var_name, default_val = expr.split(':=', 1)
                    val = get_raw_var_value(var_name)
                    if not val:
                        LOCAL_VARS[var_name] = default_val
                        return default_val
                    return val

                # 4. Alternative value: ${VAR:+alt}
                if ':+' in expr:
                    var_name, alt_val = expr.split(':+', 1)
                    val = get_raw_var_value(var_name)
                    if val:
                        return alt_val
                    return ""

                # Standard variable
                return get_raw_var_value(expr)

            if bare:
                if bare.group(0) == '$$':
                    var_name = '$$'
                else:
                    var_name = bare.group(1) or bare.group(2)
                val = get_var_value(var_name)
                if val or quote_type == 'double':
                    if quote_type is None and val:
                        import shlex
                        try:
                            split_parts = shlex.split(val)
                        except ValueError:
                            split_parts = val.split()
                        if split_parts:
                            expanded_args.extend(split_parts)
                    else:
                        expanded_args.append(val)
                continue
            elif '$' in arg:
                def var_replacer(match):
                    if match.group(0) == '$$':
                        return get_var_value('$$')
                    v = match.group(1) or match.group(2)
                    return get_var_value(v)
                arg = re.sub(_var_pat, var_replacer, arg)

            # Double-quoted: skip tilde and glob expansion
            if quote_type == 'double':
                expanded_args.append(arg)
                continue

            # 3. Tilde Expansion (unquoted only)
            if arg.startswith('~'):
                arg = os.path.expanduser(arg)

            # 4. Globbing (unquoted only)
            if globbing and ('*' in arg or '?' in arg):
                matches = glob.glob(arg)
                if matches:
                    expanded_args.extend(matches)
                else:
                    expanded_args.append(arg)
            else:
                expanded_args.append(arg)

        # Restore escaped dollar signs from sentinel \x04
        return [a.replace('\x04', '$') for a in expanded_args]

    @staticmethod
    def _command_substitute(s):
        """Replace $(...) (balanced parens) and `...` with command output.

        The whole balanced group is handed to the shell intact, so nested
        substitutions like $(echo $(echo x)) work because the shell evaluates
        the inner one itself.
        """
        if '$(' not in s and '`' not in s:
            return s

        import subprocess

        import sys

        def run(cmd):
            if sys.platform == 'win32':
                try:
                    return subprocess.check_output(
                        cmd, shell=True, text=True, stderr=subprocess.DEVNULL
                    ).rstrip('\n')
                except subprocess.CalledProcessError:
                    return ""
            
            import os
            r, w = os.pipe()
            try:
                pid = os.fork()
            except OSError:
                try:
                    return subprocess.check_output(
                        cmd, shell=True, text=True, stderr=subprocess.DEVNULL
                    ).rstrip('\n')
                except subprocess.CalledProcessError:
                    return ""

            if pid == 0:
                os.close(r)
                os.dup2(w, 1)
                os.close(w)
                
                from .executor import process_command_line
                try:
                    status = process_command_line(cmd) or 0
                    os._exit(status)
                except Exception:
                    os._exit(1)
            else:
                os.close(w)
                output = []
                try:
                    while True:
                        chunk = os.read(r, 4096)
                        if not chunk:
                            break
                        output.append(chunk.decode('utf-8', errors='ignore'))
                except Exception:
                    pass
                finally:
                    os.close(r)
                    try:
                        os.waitpid(pid, 0)
                    except ChildProcessError:
                        pass
                return ''.join(output).rstrip('\n')

        out = []
        i = 0
        n = len(s)
        while i < n:
            if s[i] == '$' and i + 1 < n and s[i + 1] == '(':
                depth = 1
                j = i + 2
                while j < n and depth > 0:
                    if s[j] == '(':
                        depth += 1
                    elif s[j] == ')':
                        depth -= 1
                    if depth == 0:
                        break
                    j += 1
                if depth == 0:
                    inner_cmd = Expander._command_substitute(s[i + 2:j])
                    out.append(run(inner_cmd))
                    i = j + 1
                    continue
                out.append(s[i])  # unbalanced — emit literally
                i += 1
            elif s[i] == '`':
                j = s.find('`', i + 1)
                if j != -1:
                    inner_cmd = Expander._command_substitute(s[i + 1:j])
                    out.append(run(inner_cmd))
                    i = j + 1
                    continue
                out.append(s[i])
                i += 1
            else:
                out.append(s[i])
                i += 1
        return ''.join(out)
