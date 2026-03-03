from .state import KISHI_SESSION, COLOR_AMBER, COLOR_RED
from prompt_toolkit.formatted_text import ANSI

class Tokenizer:
    @staticmethod
    def tokenize(cmd_line):
        """Metni tokenlara (argümanlar ve operatörlere) böler. Tırnak işaretlerini korur. argüman içindeki '&' ve '|' operatör sayılmaz."""
        
        tokens = []
        current_token = []
        in_single_quote = False
        in_double_quote = False
        escape_next = False
        
        i = 0
        while i < len(cmd_line):
            char = cmd_line[i]
            
            # 1. Escape (\) karakteri kontrolü
            if escape_next:
                current_token.append(char)
                escape_next = False
                i += 1
                continue
                
            if char == '\\':
                escape_next = True
                i += 1
                continue
                
            # 2. Tırnak işaretleri kontrolü
            if char == "'" and not in_double_quote:
                in_single_quote = not in_single_quote
                i += 1
                continue
            elif char == '"' and not in_single_quote:
                in_double_quote = not in_double_quote
                i += 1
                continue
                
            # Tırnak içindeyse her şeyi normal harf say
            if in_single_quote or in_double_quote:
                current_token.append(char)
                i += 1
                continue
                
            # 3. KORUMA ALANI OLMAYAN (Tırnaksız) YERLER
            
            # Boşluk gördüysek mevcut kelimeyi (token) bitir
            if char.isspace():
                if current_token:
                    tokens.append("".join(current_token))
                    current_token = []
                i += 1
                continue
                
            # Sabit operatörler kontrolü (<, >, >>, 2>, 2>>, 2>&1)
            # Acaba şu anki char '2' ve ondan sonraki '>' mi?
            if char == '2' and i + 1 < len(cmd_line) and cmd_line[i+1] == '>':
                if current_token:
                    tokens.append("".join(current_token))
                    current_token = []
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
                    tokens.append("".join(current_token))
                    current_token = []
                tokens.append('<')
                i += 1
                continue
                
            if char == '>':
                if current_token:
                    tokens.append("".join(current_token))
                    current_token = []
                if i + 1 < len(cmd_line) and cmd_line[i+1] == '>':
                    tokens.append('>>')
                    i += 2
                else:
                    tokens.append('>')
                    i += 1
                continue
                
            # '&' ve '|' operatörleri Fish Shell kuralı
            if char == '&':
                if i + 1 < len(cmd_line) and cmd_line[i+1] == '&':
                    if current_token:
                        tokens.append("".join(current_token))
                        current_token = []
                    tokens.append('&&')
                    i += 2
                    continue
                else:
                    prev_is_space = (i == 0) or cmd_line[i-1].isspace()
                    next_is_space = (i == len(cmd_line)-1) or cmd_line[i+1].isspace()
                    
                    if prev_is_space or next_is_space:
                        if current_token:
                            tokens.append("".join(current_token))
                            current_token = []
                        tokens.append('&')
                        i += 1
                        continue
                    else:
                        current_token.append(char)
                        i += 1
                        continue

            if char == ';':
                if current_token:
                    tokens.append("".join(current_token))
                    current_token = []
                tokens.append(';')
                i += 1
                continue
                
            if char in ('{', '}'):
                if current_token:
                    tokens.append("".join(current_token))
                    current_token = []
                tokens.append(char)
                i += 1
                continue

            if char == '|':
                if i + 1 < len(cmd_line) and cmd_line[i+1] == '|':
                    if current_token:
                        tokens.append("".join(current_token))
                        current_token = []
                    tokens.append('||')
                    i += 2
                    continue
                else:
                    if current_token:
                        tokens.append("".join(current_token))
                        current_token = []
                    tokens.append('|')
                    i += 1
                    continue
                    
            current_token.append(char)
            i += 1

        if in_single_quote or in_double_quote:
            raise ValueError("Kapanmamış tırnak işareti (Missing quotation)")
            
        if current_token:
            tokens.append("".join(current_token))
            
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
                    print(f"\n{COLOR_RED}Sözdizimi Hatası:{COLOR_RESET} Eksik tırnak işareti ({e})")
                    return []
                except KeyboardInterrupt:
                    print()
                    return []
