import os
import glob
from .state import LOCAL_VARS, ALIASES
from .lexer import QUOTE_SINGLE, QUOTE_DOUBLE

class Expander:
    @staticmethod
    def expand(arg_list):
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
            elif arg.startswith(QUOTE_DOUBLE):
                quote_type = 'double'
                arg = arg[1:]  # Strip the sentinel prefix

            # Single-quoted: emit as-is with zero expansion
            if quote_type == 'single':
                expanded_args.append(arg)
                continue

            # 1. Command Substitution (unquoted and double-quoted)
            def cmd_replacer(match):
                cmd_to_run = match.group(1) or match.group(2)
                try:
                    output = subprocess.check_output(cmd_to_run, shell=True, text=True, stderr=subprocess.DEVNULL)
                    return output.rstrip('\n')
                except subprocess.CalledProcessError:
                    return ""
            
            arg = re.sub(r'\$\(([^)]+)\)|`([^`]+)`', cmd_replacer, arg)

            # 2. Variable Expansion (unquoted and double-quoted)
            if arg.startswith('$'):
                var_name = arg[1:]
                val = LOCAL_VARS.get(var_name, os.environ.get(var_name, ALIASES.get(var_name, "")))
                if val: expanded_args.append(val)
                continue
            elif '$' in arg:
                def var_replacer(match):
                    v = match.group(1)
                    return LOCAL_VARS.get(v, os.environ.get(v, ALIASES.get(v, "")))
                arg = re.sub(r'\$([A-Za-z0-9_]+)', var_replacer, arg)

            # Double-quoted: skip tilde and glob expansion
            if quote_type == 'double':
                expanded_args.append(arg)
                continue

            # 3. Tilde Expansion (unquoted only)
            if arg.startswith('~/') or arg == '~':
                arg = os.path.expanduser(arg)

            # 4. Globbing (unquoted only)
            if '*' in arg or '?' in arg:
                matches = glob.glob(arg)
                if matches:
                    expanded_args.extend(matches)
                else:
                    expanded_args.append(arg)
            else:
                expanded_args.append(arg)
                
        return expanded_args
