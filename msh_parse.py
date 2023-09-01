from lark import Lark, Transformer, v_args
import operator
from lark.exceptions import VisitError, UnexpectedCharacters, UnexpectedEOF

grammar = r'''
?start: expr
ident: CNAME
int: SIGNED_INT
float: SIGNED_FLOAT
str: ESCAPED_STRING
?number: int | float
?arg: expr | str
?expr: number
     | ident -> get
     | ident "=" expr -> set
     | ident "(" [arg ("," arg)*] ")" -> call
     | "(" expr ")"
     | expr "+" expr -> add
     | expr "-" expr -> sub
     | expr "*" expr -> mul
     | expr "/" expr -> div
%import common.SIGNED_INT
%import common.SIGNED_FLOAT
%import common.WS
%import common.CNAME
%import common.ESCAPED_STRING
%ignore WS
'''


@v_args(inline=True)
class Msh_Parse(Transformer):
    vars = {}
    ident = str
    int = int
    float = float
    add = operator.add
    str = lambda _, s: s[1:-1]

    def call(self, n, *v):
        try:
            return getattr(self, n)(*v)
        except:
            return None

    def echo(self, *v):
        print(*v)

    def min(self, *v):
        return min(*v)

    def set(self, n, v):
        self.vars[n] = v
        return v

    def get(self, n):
        try:
            return self.vars[n]
        except KeyError:
            raise UnboundLocalError(f"{n} Var Not Found")


parser = Lark(grammar)
transformer = Msh_Parse()

while 1:
    try:
        s = input(">")
    except EOFError:
        print("LOL")
        continue
    except KeyboardInterrupt:
        exit()
    try:
        tree = parser.parse(s)
        print(transformer.transform(tree))
    except (UnexpectedCharacters, UnexpectedEOF, VisitError) as e:
        try:
            print(e.orig_exc)
        except:
            print(e)
        continue
