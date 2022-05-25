import lark 

grammaire = lark.Lark("""
variables : IDENTIFIANT ("," IDENTIFIANT)*
expr : IDENTIFIANT -> variable | NUMBER -> nombre | expr OP expr -> binexpr 
| "(" expr ")" -> parenexpr
cmd : IDENTIFIANT "=" expr ";"-> assignment | "tant que" "(" expr ")" "{" bloc "}" -> while
    | "si" "(" expr ")" "{" bloc "}" -> if | "affiche" "(" expr ")" ";"-> printf 
bloc : (cmd)*
prog : "principale" "(" variables ")" "{" bloc "renvoie" "(" expr ")" ";" "}"
NUMBER : /[0-9]+/
OP : /[+\*>-]/
IDENTIFIANT : /[a-zA-Z][a-zA-Z0-9]*/
%import common.WS 
%ignore WS
""", start = "prog")
#WS = White Space
#binexpr et parentexpr permet d'être plus précis dans le type d'expression utilisée

cpt = iter(range(10000)) #compteur pour while
op2asm = {"+": "add", "-": "sub", "*": "imul"}

def add_ind():
    global ind
    return ("".join("   " for i in range(ind)))

def pp_var(vars):
    return ", ".join([t.value for t in vars.children])

def pp_expr(expr):
    if expr.data in {"variable", "nombre"}:
        return expr.children[0].value
    elif expr.data == "binexpr":
        e1 = pp_expr(expr.children[0])
        e2= pp_expr(expr.children[2])
        op = expr.children[1].value
        return f"{e1} {op} {e2}"
    elif expr.data == "parenexpr" :
        return f"({pp_expr(expr.children[0])})"
    else : 
        raise Exception("Not Implemented")

def pp_cmd(cmd):
    global ind
    if cmd.data == "assignment":
        lhs = cmd.children[0].value
        rhs = pp_expr(cmd.children[1])
        espace = add_ind()
        return f"{espace}{lhs} = {rhs};"
    elif cmd.data == "printf":
        espace = add_ind()
        return f"{espace}affiche({pp_expr(cmd.children[0])});\n"
    elif cmd.data == "while":
        e = pp_expr(cmd.children[0])
        b = pp_bloc(cmd.children[1])
        espace = add_ind()
        ind += 1
        return f"{espace}tant que ({e}) {{ \n{b}}} \n"
    elif cmd.data == "if":
        e = pp_expr(cmd.children[0])
        b = pp_bloc(cmd.children[1])
        espace = add_ind()
        ind += 1
        return f"{espace}si ({e}) {{ \n{b}}}\n"
    else :
        raise Exception("Not Implemented")
    return ""

def pp_bloc(bloc):
    return "\n".join([pp_cmd(t) for t in bloc.children])

def pp_prg(prog): #pretty printer = jolie afficheur
    global ind #pour l'indentation
    ind = 1
    vars = pp_var(prog.children[0])
    bloc = pp_bloc(prog.children[1])
    ret = pp_expr(prog.children[2])
    return f"principale({vars}) {{ \n{bloc}   renvoie({ret}); \n}}"

prg = grammaire.parse("""principale(X,Y) { 
    si (X) { 
        X = X+1;
        Y = Y+X;
        affiche(X); 
        } 
    renvoie(Y+1);
    }""")


prg2 = grammaire.parse(pp_prg(prg))
#print(prg2 == prg)
#print(pp_prg(prg))

#print(prg)
#Il faut tester tout quand on modifie la grammaire (X, 1333, X+133, ...)
#X+133 renvoie : Tree(rule:expr,[X,+,133]) (en moche avec des tree, token,expr, number, id, ...)
#exemple : principale(X,Y) { si (X) { affiche(X); } renvoie(Y);}
#amélioration possible : rajouter les sauts de ligne et les indentations 

def assembl_prog(prog):
    vars = pp_var(prog.children[0])
    bloc = assembl_bloc(prog.children[1])
    ret = assembl_expr(prog.children[2])
    return f"principale({vars}) {{ \n{bloc}   renvoie({ret}); \n}}" #mettre les global, section,...

def assembl_expr(expr):
    if expr.data == "variable":
        return f"mov rax,[{expr.children[0].value}]\n"
    elif expr.data == "nombre":
        return f"mov rax,{expr.children[0].value}\n"
    elif expr.data == "binexpr":
        e1 = assembl_expr(expr.children[0])
        e2= assembl_expr(expr.children[2])
        op = expr.children[1].value
        if op == "+":
            return f"{e1}\npush rax\n{e2}\npop rbx\npop rax\nadd rax,rbx\n"
    elif expr.data == "parenexpr" :
        return f"{assembl_expr(expr.children[0])}\n"
    else : 
        print(expr.data)
        raise Exception("Not Implemented")

def assembl_cmd(cmd):
    if cmd.data == "assignment":
        lhs = cmd.children[0].value
        rhs = cmd.children[1]
        return f"{assembl_expr(rhs)} mov [{lhs}],rax\n"
    elif cmd.data == "printf":
        return f"{assembl_expr(cmd.children[0])} mov rdi,fmt\nmov rsi,rax\nxor rax,rax\ncall printf\n"
    elif cmd.data == "while":
        return f"{assembl_expr(cmd.children[0])} cmp rax,0\njz fin\n{assembl_expr(cmd.children[1])} jmp debut\n"
    elif cmd.data == "if":
        e = cmd.children[0]
        b = cmd.children[1]
        return f"{assembl_expr(e)} cpm rax,0\njz fin\n{assembl_expr(b)} jmp debut\n"
    else :
        raise Exception("Not Implemented")
    return ""

def assembl_bloc(bloc):
        return "\n".join([assembl_cmd(t) for t in bloc.children])

#print(assembl_prog(prg))

def var_list(ast):
    if isinstance(ast, lark.Token):
        if ast.type == "IDENTIFIANT":
            return {ast.value}
        else:
            return set()
    s = set()
    for c in ast.children:
        s.update(var_list(c))
    return s

def compile(prg):
    with open("moule.asm") as f:
        code = f.read()
        var_decl = "\n".join([f"{x}: dq 0" for x in var_list(prg)])
        code  = code.replace("VAR_DECL", var_decl)
        code = code.replace("RETURN", compile_expr(prg.children[2]))
        code = code.replace("BODY", compile_bloc(prg.children[1]))
        code = code.replace("VAR_INIT", compile_vars(prg.children[0]))
        
        return code

def compile_vars(ast):
    s = ""
    for i in range(len(ast.children)):
        s += f"mov rbx, [rbp-0x10]\nmov rdi,[rbx+{8*(i+1)}]\ncall atoi\nmov [{ast.children[i].value}], rax\n"
    return s

def compile_expr(expr):
    if expr.data == "variable":
        return f"mov rax,[{expr.children[0].value}]"
    elif expr.data == "nombre":
        return f"mov rax,{expr.children[0].value}"
    elif expr.data == "binexpr":
        e1 = compile_expr(expr.children[0])
        e2 = compile_expr(expr.children[2])
        op = expr.children[1].value
        return f"{e2}\npush rax\n{e1}\npop rbx\n{op2asm[expr.children[1].value]} rax,rbx\n"
    elif expr.data == "parenexpr" :
        return compile_expr(expr.children[0])
    else : 
        raise Exception("Not Implemented")


def compile_cmd(cmd):
    if cmd.data == "assignment":
        lhs = cmd.children[0].value
        rhs = compile_expr(cmd.children[1])
        return f"{rhs}\nmov [{lhs}],rax\n"
    elif cmd.data == "printf":
        e = compile_expr(cmd.children[0])
        return f"{e}\nmov rdi,fmt\nmov rsi,rax\nxor rax,rax\ncall printf\n"
    elif cmd.data == "while":
        e = compile_expr(cmd.children[0])
        b = compile_bloc(cmd.children[1])
        index = next(cpt)
        return f"debut{index}:{e}\ncmp rax,0\njz fin{index}\n{b}\njmp debut{index}\nfin{index}:\n"
    elif cmd.data == "if":
        e = compile_expr(cmd.children[0])
        b = compile_expr(cmd.children[1])
        index = next(cpt)
        return f"{e}:\ncmp rax,0\njzfin{index}\n{b}\nfin{index}:\n"
    else :
        raise Exception("Not Implemented")
    #return ""

def compile_bloc(bloc):
    return "\n".join([compile_cmd(t) for t in bloc.children])

prg3 = grammaire.parse("""principale(X,Y) {
tant que(X){
    Z=3;
    X = X - 1; Y = Y+1; 
    affiche(X);
}
renvoie(Y+1);}""")
prg4 = grammaire.parse("""principale(X) {
    renvoie(X);}""")

print(compile(prg3))
