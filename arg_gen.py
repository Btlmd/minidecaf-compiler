ARG_COUNT = 127

TEMPLATE = """
int %s(%s){
    return %s;
}

int main() {
    %s;
    return %s(%s);
}
"""

name = "wow_so_many_args"
params = ",\n    ".join(["int arg%02d" % i for i in range(ARG_COUNT)])
values = "+\n    ".join(["arg%02d" % i for i in range(ARG_COUNT)])
inits = ";\n    ".join(["int var%02d = %d" % (i, i) for i in range(ARG_COUNT)])
calls = ",\n    ".join(["var%02d" % i for i in range(ARG_COUNT)])

print(TEMPLATE % (
    name,
    params,
    values,
    inits,
    name,
    calls
))


