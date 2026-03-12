import os
import glob
from .state import LOCAL_VARS, ALIASES

class Expander:
    @staticmethod
    def expand(arg_list):
        """Expands globs (*, ?), variables ($VAR) and command substitutions ($(cmd) / `cmd`)"""
        import re
        import subprocess

        expanded_args = []
        for arg in arg_list:
            # 1. Command Substitution
            def cmd_replacer(match):
                cmd_to_run = match.group(1) or match.group(2)
                try:
                    output = subprocess.check_output(cmd_to_run, shell=True, text=True, stderr=subprocess.DEVNULL)
                    return output.rstrip('\n')
                except subprocess.CalledProcessError:
                    return ""
            
            arg = re.sub(r'\$\(([^)]+)\)|`([^`]+)`', cmd_replacer, arg)

            # 2. Variable Expansion
            if arg.startswith('$'):
                var_name = arg[1:]
                val = LOCAL_VARS.get(var_name, os.environ.get(var_name, ALIASES.get(var_name, "")))
                if val: expanded_args.append(val)
                continue
            elif '$' in arg:
                def var_replacer(match):
                    v = match.group(1)
                    return LOCAL_VARS.get(v, os.environ.get(v, ""))
                arg = re.sub(r'\$([A-Za-z0-9_]+)', var_replacer, arg)

            # 3. Tilde Expansion
            if arg.startswith('~/') or arg == '~':
                arg = os.path.expanduser(arg)

            # 4. Globbing
            if '*' in arg or '?' in arg:
                matches = glob.glob(arg)
                if matches:
                    expanded_args.extend(matches)
                else:
                    expanded_args.append(arg)
            else:
                expanded_args.append(arg)
                
        return expanded_args
