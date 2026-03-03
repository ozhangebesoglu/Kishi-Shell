class ASTNode:
    pass

class CommandNode(ASTNode):
    def __init__(self):
        self.args = []
        self.in_file = None
        self.out_file = None
        self.out_append = False
        self.err_file = None
        self.err_append = False
        self.err_to_out = False
        
class PipelineNode(ASTNode):
    def __init__(self):
        self.commands = [] # List of CommandNode
        self.is_background = False

class LogicNode(ASTNode):
    def __init__(self, left, operator, right):
        self.left = left # PipelineNode veya LogicNode
        self.operator = operator # '&&' veya '||'
        self.right = right

class SequenceNode(ASTNode):
    def __init__(self):
        self.statements = [] # List of ASTNodes

class IfNode(ASTNode):
    def __init__(self, condition_ast, then_ast, elifs, else_ast):
        self.condition_ast = condition_ast
        self.then_ast = then_ast
        self.elifs = elifs # List of (cond_ast, then_ast)
        self.else_ast = else_ast

class WhileNode(ASTNode):
    def __init__(self, condition_ast, body_ast):
        self.condition_ast = condition_ast
        self.body_ast = body_ast

class ForNode(ASTNode):
    def __init__(self, var_name, iter_items, body_ast):
        self.var_name = var_name
        self.iter_items = iter_items
        self.body_ast = body_ast

class FunctionDefNode(ASTNode):
    def __init__(self, func_name, body_ast):
        self.func_name = func_name
        self.body_ast = body_ast

class Parser:
    @staticmethod
    def parse(tokens):
        """Token listesinden Recursive Inis ile Sequence/Logic/Pipeline AST'si çıkarır"""
        if not tokens: return None
        
        class TokenStream:
            def __init__(self, toks):
                self.toks = toks
                self.pos = 0
            
            def peek(self):
                if self.pos < len(self.toks): return self.toks[self.pos]
                return None
            
            def consume(self):
                t = self.peek()
                self.pos += 1
                return t

        stream = TokenStream(tokens)
        
        def parse_sequence(end_tokens=None):
            if end_tokens is None: end_tokens = []
            seq = SequenceNode()
            current_statement_tokens = []
            
            def push_statement():
                if current_statement_tokens:
                    ast = split_by_logic(current_statement_tokens)
                    if ast: seq.statements.append(ast)
                    current_statement_tokens.clear()

            while stream.peek() is not None:
                token = stream.peek()
                
                if token in end_tokens:
                    break
                    
                if token == ';':
                    stream.consume()
                    push_statement()
                    continue
                    
                if token == 'if':
                    push_statement()
                    stream.consume() # consume 'if'
                    
                    cond_toks = []
                    while stream.peek() not in ('then', ';', None):
                        cond_toks.append(stream.consume())
                    if stream.peek() == ';': stream.consume() # ignore optional ;
                    cond_ast = split_by_logic(cond_toks)
                    
                    if stream.peek() == 'then': stream.consume()
                    
                    then_ast = parse_sequence(end_tokens=['elif', 'else', 'fi'])
                    
                    elif_asts = []
                    while stream.peek() == 'elif':
                        stream.consume()
                        e_cond_toks = []
                        while stream.peek() not in ('then', ';', None):
                            e_cond_toks.append(stream.consume())
                        if stream.peek() == ';': stream.consume()
                        e_cond_ast = split_by_logic(e_cond_toks)
                        if stream.peek() == 'then': stream.consume()
                        e_then_ast = parse_sequence(end_tokens=['elif', 'else', 'fi'])
                        elif_asts.append((e_cond_ast, e_then_ast))
                        
                    else_ast = None
                    if stream.peek() == 'else':
                        stream.consume()
                        else_ast = parse_sequence(end_tokens=['fi'])
                        
                    if stream.peek() == 'fi':
                        stream.consume()
                        
                    seq.statements.append(IfNode(cond_ast, then_ast, elif_asts, else_ast))
                    continue

                if token == 'while':
                    push_statement()
                    stream.consume()
                    
                    cond_toks = []
                    while stream.peek() not in ('do', ';', None):
                        cond_toks.append(stream.consume())
                    if stream.peek() == ';': stream.consume()
                    cond_ast = split_by_logic(cond_toks)
                    
                    if stream.peek() == 'do': stream.consume()
                    
                    body_ast = parse_sequence(end_tokens=['done'])
                    
                    if stream.peek() == 'done': stream.consume()
                    
                    seq.statements.append(WhileNode(cond_ast, body_ast))
                    continue

                if token == 'for':
                    push_statement()
                    stream.consume()
                    
                    var_name = stream.consume() if stream.peek() else "i"
                    if stream.peek() == 'in': stream.consume()
                    
                    iter_items = []
                    while stream.peek() not in (';', 'do', None):
                        iter_items.append(stream.consume())
                        
                    if stream.peek() == ';': stream.consume()
                    if stream.peek() == 'do': stream.consume()
                    
                    body_ast = parse_sequence(end_tokens=['done'])
                    
                    if stream.peek() == 'done': stream.consume()
                    
                    seq.statements.append(ForNode(var_name, iter_items, body_ast))
                    continue
                    
                if stream.peek() and stream.peek() == '()':
                    pass
                    
                if token.endswith('()'):
                    push_statement()
                    func_name = token[:-2]
                    stream.consume() # myfunc()
                    
                    if stream.peek() == '{': stream.consume()
                    body_ast = parse_sequence(end_tokens=['}'])
                    if stream.peek() == '}': stream.consume()
                    
                    seq.statements.append(FunctionDefNode(func_name, body_ast))
                    continue
                    
                if stream.pos + 1 <= len(stream.toks) and stream.peek() == '()':
                    push_statement()
                    func_name = token
                    stream.consume() # myfunc
                    stream.consume() # ()
                    
                    if stream.peek() == '{': stream.consume()
                    body_ast = parse_sequence(end_tokens=['}'])
                    if stream.peek() == '}': stream.consume()
                    
                    seq.statements.append(FunctionDefNode(func_name, body_ast))
                    continue

                current_statement_tokens.append(stream.consume())
                
            push_statement()
            return seq

        def split_by_logic(toks, force_bg=False):
            out_bg = False
            if toks and toks[-1] == '&':
                out_bg = True
                toks = toks[:-1]

            for i in range(len(toks)-1, -1, -1):
                if toks[i] == '&':
                    left = split_by_logic(toks[:i], force_bg=True)
                    right = split_by_logic(toks[i+1:])
                    return LogicNode(left, '&', right)
                    
                if toks[i] in ('&&', '||'):
                    left = split_by_logic(toks[:i])
                    right = split_by_logic(toks[i+1:])
                    return LogicNode(left, toks[i], right)
                    
            return parse_pipeline(toks, out_bg or force_bg)

        def parse_pipeline(toks, is_bg):
            pipe_node = PipelineNode()
            pipe_node.is_background = is_bg
            
            cmd_toks_list = []
            curr = []
            for t in toks:
                if t == '|':
                    cmd_toks_list.append(curr)
                    curr = []
                else:
                    curr.append(t)
            cmd_toks_list.append(curr)
            
            for c_toks in cmd_toks_list:
                cmd_node = CommandNode()
                i = 0
                while i < len(c_toks):
                    if c_toks[i] == '<' and i+1 < len(c_toks):
                        cmd_node.in_file = c_toks[i+1]
                        i += 2
                    elif c_toks[i] == '>' and i+1 < len(c_toks):
                        cmd_node.out_file = c_toks[i+1]
                        i += 2
                    elif c_toks[i] == '>>' and i+1 < len(c_toks):
                        cmd_node.out_file = c_toks[i+1]
                        cmd_node.out_append = True
                        i += 2
                    elif c_toks[i] == '2>' and i+1 < len(c_toks):
                        cmd_node.err_file = c_toks[i+1]
                        i += 2
                    elif c_toks[i] == '2>>' and i+1 < len(c_toks):
                        cmd_node.err_file = c_toks[i+1]
                        cmd_node.err_append = True
                        i += 2
                    elif c_toks[i] == '2>&1':
                        cmd_node.err_to_out = True
                        i += 1
                    else:
                        cmd_node.args.append(c_toks[i])
                        i += 1
                        
                if cmd_node.args:
                    pipe_node.commands.append(cmd_node)
            return pipe_node

        return parse_sequence()
