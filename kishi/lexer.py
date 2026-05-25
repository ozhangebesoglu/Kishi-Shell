from .state import KISHI_SESSION, COLOR_AMBER, COLOR_RED
from prompt_toolkit.formatted_text import ANSI

# Sentinel prefixes for quote-type metadata
QUOTE_SINGLE = '\x01'  # Token was inside single quotes (no expansion)
QUOTE_DOUBLE = '\x02'  # Token was inside double quotes (variable expansion only)
QUOTE_DOLLAR_SINGLE = '\x03'  # Token was inside $'...' (C-style escape, no expansion)

class Tokenizer:
    @staticmethod
    def _process_dollar_single_escapes(raw):
        """Process C-style escape sequences inside $'...' strings."""
        result = []
        i = 0
        while i < len(raw):
            if raw[i] != '\\':
                result.append(raw[i])
                i += 1
                continue
            # Escape sequence
            if i + 1 >= len(raw):
                result.append('\\')
                break
            c = raw[i + 1]
            if c == '\\':
                result.append('\\')
                i += 2
            elif c == "'":
                result.append("'")
                i += 2
            elif c == '"':
                result.append('"')
                i += 2
            elif c == 'a':
                result.append('\a')
                i += 2
            elif c == 'b':
                result.append('\b')
                i += 2
            elif c == 'f':
                result.append('\f')
                i += 2
            elif c == 'n':
                result.append('\n')
                i += 2
            elif c == 'r':
                result.append('\r')
                i += 2
            elif c == 't':
                result.append('\t')
                i += 2
            elif c == 'v':
                result.append('\v')
                i += 2
            elif c == 'x':
                # \xHH — hex byte
                hex_str = raw[i+2:i+4]
                if len(hex_str) >= 1:
                    # Consume as many hex digits as available (up to 2)
                    valid = ''
                    for h in hex_str:
                        if h in '0123456789abcdefABCDEF':
                            valid += h
                        else:
                            break
                    if valid:
                        result.append(chr(int(valid, 16)))
                        i += 2 + len(valid)
                    else:
                        result.append('\\x')
                        i += 2
                else:
                    result.append('\\x')
                    i += 2
            elif c == 'u':
                # \uHHHH — 4-digit unicode
                hex_str = raw[i+2:i+6]
                valid = ''
                for h in hex_str:
                    if h in '0123456789abcdefABCDEF':
                        valid += h
                    else:
                        break
                if valid:
                    result.append(chr(int(valid, 16)))
                    i += 2 + len(valid)
                else:
                    result.append('\\u')
                    i += 2
            elif c == 'U':
                # \UHHHHHHHH — 8-digit unicode
                hex_str = raw[i+2:i+10]
                valid = ''
                for h in hex_str:
                    if h in '0123456789abcdefABCDEF':
                        valid += h
                    else:
                        break
                if valid:
                    result.append(chr(int(valid, 16)))
                    i += 2 + len(valid)
                else:
                    result.append('\\U')
                    i += 2
            elif c == '0':
                # \0nnn — octal byte
                oct_str = raw[i+2:i+5]
                valid = ''
                for o in oct_str:
                    if o in '01234567':
                        valid += o
                    else:
                        break
                if valid:
                    result.append(chr(int(valid, 8)))
                    i += 2 + len(valid)
                else:
                    result.append('\x00')
                    i += 2
            else:
                # Unknown escape — keep backslash + char
                result.append('\\' + c)
                i += 2
        return ''.join(result)

    @staticmethod
    def _quote_prefix(has_dollar_single, has_single, has_double):
        """Pick the sentinel prefix for a token. When a token mixes single and
        double quotes, double wins so the $VAR part still expands."""
        if has_dollar_single:
            return QUOTE_DOLLAR_SINGLE
        if has_double:
            return QUOTE_DOUBLE
        if has_single:
            return QUOTE_SINGLE
        return ''

    @staticmethod
    def tokenize(cmd_line):
        """Splits text into tokens (arguments and operators). Preserves quoted strings. '&' and '|' inside arguments are not treated as operators."""
        
        tokens = []
        current_token = []
        in_single_quote = False
        in_double_quote = False
        escape_next = False
        # Track the quote type that covers the current token
        token_has_single = False
        token_has_dollar_single = False
        token_has_double = False
        # Set when '&>' is seen; a trailing '2>&1' is appended at the end.
        ampersand_redirect = False
        braced_var_depth = 0
        paren_sub_depth = 0

        i = 0
        while i < len(cmd_line):
            char = cmd_line[i]
            
            # 1. Escape (\) character handling
            if escape_next:
                if in_double_quote and char == '$':
                    current_token.append('\x04')  # Use sentinel to prevent variable expansion
                else:
                    current_token.append(char)
                escape_next = False
                i += 1
                continue
                
            if char == '\\':
                if in_double_quote:
                    # Double quotes escape only: ", \, $, `
                    if i + 1 < len(cmd_line) and cmd_line[i+1] in ('"', '\\', '$', '`'):
                        escape_next = True
                        i += 1
                        continue
                    else:
                        current_token.append('\\')
                        i += 1
                        continue
                elif in_single_quote:
                    # Single quotes do NOT escape anything
                    current_token.append('\\')
                    i += 1
                    continue
                else:
                    escape_next = True
                    i += 1
                    continue
                
            # 2. $'...' (Dollar-Single-Quote / ANSI-C Quoting)
            if char == '$' and i + 1 < len(cmd_line) and cmd_line[i+1] == "'" and not in_single_quote and not in_double_quote:
                i += 2  # skip $'
                raw_chars = []
                ds_escape = False
                while i < len(cmd_line):
                    if ds_escape:
                        raw_chars.append('\\' + cmd_line[i])
                        ds_escape = False
                        i += 1
                        continue
                    if cmd_line[i] == '\\':
                        ds_escape = True
                        i += 1
                        continue
                    if cmd_line[i] == "'":
                        i += 1  # skip closing '
                        break
                    raw_chars.append(cmd_line[i])
                    i += 1
                else:
                    raise ValueError("Unclosed $' quotation")
                processed = Tokenizer._process_dollar_single_escapes(''.join(raw_chars))
                if processed:
                    current_token.append(processed)
                    token_has_single = True  # reuse single-quote sentinel behavior for prefix
                    # Override: mark as dollar-single specifically
                    token_has_dollar_single = True
                continue

            # 3. Quote character handling
            if char == "'" and not in_double_quote:
                in_single_quote = not in_single_quote
                if in_single_quote:
                    token_has_single = True
                i += 1
                continue
            elif char == '"' and not in_single_quote:
                in_double_quote = not in_double_quote
                if in_double_quote:
                    token_has_double = True
                i += 1
                continue
                
            # Inside quotes, treat everything as a regular character
            if in_single_quote or in_double_quote:
                current_token.append(char)
                i += 1
                continue
                
            # If inside braced variable or command substitution, treat everything as regular character
            # but keep track of nesting depths
            if braced_var_depth > 0:
                if char == '}':
                    braced_var_depth -= 1
                elif char == '{':
                    braced_var_depth += 1
                current_token.append(char)
                i += 1
                continue

            if paren_sub_depth > 0:
                if char == ')':
                    paren_sub_depth -= 1
                elif char == '(':
                    paren_sub_depth += 1
                current_token.append(char)
                i += 1
                continue

            # Detect the start of a braced variable `${...}`
            if char == '{' and current_token and current_token[-1] == '$':
                braced_var_depth += 1
                current_token.append(char)
                i += 1
                continue

            # Detect the start of a command substitution `$(...)`
            if char == '(' and current_token and current_token[-1] == '$':
                paren_sub_depth += 1
                current_token.append(char)
                i += 1
                continue
                
            # 3. UNQUOTED (unprotected) regions
            
            # Whitespace ends the current token
            if char.isspace():
                if current_token:
                    prefix = Tokenizer._quote_prefix(token_has_dollar_single, token_has_single, token_has_double)
                    tokens.append(prefix + "".join(current_token))
                    current_token = []
                    token_has_single = False
                    token_has_dollar_single = False
                    token_has_double = False
                i += 1
                continue
                
            # Comment: '#' at a word boundary starts a comment until end of line.
            # '#' inside a word (current_token non-empty) stays literal.
            if char == '#' and not current_token:
                break

            # &> — redirect both stdout and stderr. Emit '>' here; a trailing
            # '2>&1' is appended after tokenizing so the parser wires up err->out.
            if char == '&' and i + 1 < len(cmd_line) and cmd_line[i+1] == '>':
                tokens.append('>')
                ampersand_redirect = True
                i += 2
                continue

            # Numbered fd redirect: '1>' / '1>>' map to stdout '>' / '>>'.
            if char == '1' and i + 1 < len(cmd_line) and cmd_line[i+1] == '>':
                if current_token:
                    prefix = Tokenizer._quote_prefix(token_has_dollar_single, token_has_single, token_has_double)
                    tokens.append(prefix + "".join(current_token))
                    current_token = []
                    token_has_single = token_has_dollar_single = token_has_double = False
                if i + 2 < len(cmd_line) and cmd_line[i+2] == '>':
                    tokens.append('>>')
                    i += 3
                else:
                    tokens.append('>')
                    i += 2
                continue

            # Fixed operator handling (<, >, >>, 2>, 2>>, 2>&1)
            # Check if current char is '2' followed by '>'
            if char == '2' and i + 1 < len(cmd_line) and cmd_line[i+1] == '>':
                if current_token:
                    prefix = Tokenizer._quote_prefix(token_has_dollar_single, token_has_single, token_has_double)
                    tokens.append(prefix + "".join(current_token))
                    current_token = []
                    token_has_single = False
                    token_has_dollar_single = False
                    token_has_double = False
                if i + 3 < len(cmd_line) and cmd_line[i+1:i+4] == '>&1':
                    tokens.append('2>&1')
                    i += 4
                    continue
                elif i + 2 < len(cmd_line) and cmd_line[i+1:i+3] == '>>':
                    tokens.append('2>>')
                    i += 3
                    continue
                else:
                    tokens.append('2>')
                    i += 2
                    continue
            
            if char == '<':
                if current_token:
                    prefix = Tokenizer._quote_prefix(token_has_dollar_single, token_has_single, token_has_double)
                    tokens.append(prefix + "".join(current_token))
                    current_token = []
                    token_has_single = False
                    token_has_dollar_single = False
                    token_has_double = False
                tokens.append('<')
                i += 1
                continue
                
            if char == '>':
                if current_token:
                    prefix = Tokenizer._quote_prefix(token_has_dollar_single, token_has_single, token_has_double)
                    tokens.append(prefix + "".join(current_token))
                    current_token = []
                    token_has_single = False
                    token_has_dollar_single = False
                    token_has_double = False
                if i + 1 < len(cmd_line) and cmd_line[i+1] == '>':
                    tokens.append('>>')
                    i += 2
                else:
                    tokens.append('>')
                    i += 1
                continue
                
            # '&' and '|' operators (Fish Shell convention)
            if char == '&':
                if i + 1 < len(cmd_line) and cmd_line[i+1] == '&':
                    if current_token:
                        prefix = Tokenizer._quote_prefix(token_has_dollar_single, token_has_single, token_has_double)
                        tokens.append(prefix + "".join(current_token))
                        current_token = []
                        token_has_single = False
                        token_has_dollar_single = False
                        token_has_double = False
                    tokens.append('&&')
                    i += 2
                    continue
                else:
                    prev_is_space = (i == 0) or cmd_line[i-1].isspace()
                    next_is_space = (i == len(cmd_line)-1) or cmd_line[i+1].isspace()
                    
                    if prev_is_space or next_is_space:
                        if current_token:
                            prefix = Tokenizer._quote_prefix(token_has_dollar_single, token_has_single, token_has_double)
                            tokens.append(prefix + "".join(current_token))
                            current_token = []
                            token_has_single = False
                            token_has_dollar_single = False
                            token_has_double = False
                        tokens.append('&')
                        i += 1
                        continue
                    else:
                        current_token.append(char)
                        i += 1
                        continue

            if char == ';':
                if current_token:
                    prefix = Tokenizer._quote_prefix(token_has_dollar_single, token_has_single, token_has_double)
                    tokens.append(prefix + "".join(current_token))
                    current_token = []
                    token_has_single = False
                    token_has_dollar_single = False
                    token_has_double = False
                if i + 1 < len(cmd_line) and cmd_line[i+1] == ';':
                    tokens.append(';;')
                    i += 2
                else:
                    tokens.append(';')
                    i += 1
                continue
                
            if char in ('{', '}', '(', ')'):
                if current_token:
                    prefix = Tokenizer._quote_prefix(token_has_dollar_single, token_has_single, token_has_double)
                    tokens.append(prefix + "".join(current_token))
                    current_token = []
                    token_has_single = False
                    token_has_dollar_single = False
                    token_has_double = False
                tokens.append(char)
                i += 1
                continue

            if char == '|':
                if i + 1 < len(cmd_line) and cmd_line[i+1] == '|':
                    if current_token:
                        prefix = Tokenizer._quote_prefix(token_has_dollar_single, token_has_single, token_has_double)
                        tokens.append(prefix + "".join(current_token))
                        current_token = []
                        token_has_single = False
                        token_has_dollar_single = False
                        token_has_double = False
                    tokens.append('||')
                    i += 2
                    continue
                else:
                    if current_token:
                        prefix = Tokenizer._quote_prefix(token_has_dollar_single, token_has_single, token_has_double)
                        tokens.append(prefix + "".join(current_token))
                        current_token = []
                        token_has_single = False
                        token_has_dollar_single = False
                        token_has_double = False
                    tokens.append('|')
                    i += 1
                    continue
                    
            current_token.append(char)
            i += 1

        if in_single_quote or in_double_quote:
            raise ValueError("Unclosed quotation mark")
            
        if current_token:
            prefix = Tokenizer._quote_prefix(token_has_dollar_single, token_has_single, token_has_double)
            tokens.append(prefix + "".join(current_token))

        if ampersand_redirect:
            tokens.append('2>&1')

        return tokens

    @staticmethod
    def wrap_tokenize(cmd_line):
        while True:
            try:
                return Tokenizer.tokenize(cmd_line)
            except ValueError as e:
                try:
                    import kishi.state
                    if kishi.state.KISHI_SESSION:
                        extra_line = kishi.state.KISHI_SESSION.prompt(ANSI(f"{COLOR_AMBER}> {COLOR_RESET}"))
                    else:
                        extra_line = input("> ")
                    cmd_line += "\n" + extra_line
                except EOFError:
                    print(f"\n{COLOR_RED}Syntax Error:{COLOR_RESET} Unclosed quotation mark ({e})")
                    return []
                except KeyboardInterrupt:
                    print()
                    return []
