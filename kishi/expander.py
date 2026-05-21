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
            _var_pat = r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z0-9_]+)'
            bare = re.fullmatch(_var_pat, arg)
            if bare:
                var_name = bare.group(1) or bare.group(2)
                val = LOCAL_VARS.get(var_name, os.environ.get(var_name, ALIASES.get(var_name, "")))
                if val or quote_type == 'double':
                    expanded_args.append(val)
                continue
            elif '$' in arg:
                def var_replacer(match):
                    v = match.group(1) or match.group(2)
                    return LOCAL_VARS.get(v, os.environ.get(v, ALIASES.get(v, "")))
                arg = re.sub(_var_pat, var_replacer, arg)

            # Double-quoted: skip tilde and glob expansion
            if quote_type == 'double':
                expanded_args.append(arg)
                continue

            # 3. Tilde Expansion (unquoted only)
            if arg.startswith('~/') or arg == '~':
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

        return expanded_args

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

        def run(cmd):
            try:
                return subprocess.check_output(
                    cmd, shell=True, text=True, stderr=subprocess.DEVNULL
                ).rstrip('\n')
            except subprocess.CalledProcessError:
                return ""

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
                    out.append(run(s[i + 2:j]))
                    i = j + 1
                    continue
                out.append(s[i])  # unbalanced — emit literally
                i += 1
            elif s[i] == '`':
                j = s.find('`', i + 1)
                if j != -1:
                    out.append(run(s[i + 1:j]))
                    i = j + 1
                    continue
                out.append(s[i])
                i += 1
            else:
                out.append(s[i])
                i += 1
        return ''.join(out)
