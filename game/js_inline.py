#!/usr/bin/python2.5
# modified from sexp.py, which can be found at http://code.google.com/p/pynarcissus/

import sys
import jsparser

################################################################################
# class Scope
################################################################################

# keeps track of generated local variables
class Scope:
	def __init__(self):
		self.vars = [[]]
		self.locals = [set()]

	# enter a new scope, forget about any local variables created before
	def push(self):
		self.vars.append([])
		self.locals.append(set())

	# returns the local variables allocated
	def pop(self):
		return sorted(list(self.locals.pop()), key=lambda x: int(x[1:]))

	# allocate a local variable
	def alloc(self):
		t = "_%d"
		i = 0
		while (t % i) in self.vars[-1]:
			i += 1
		var = t % i
		self.locals[-1].add(var)
		self.vars[-1].append(var)
		return var

	# free a local variable (to minimize the number used)
	def free(self, var):
		self.vars[-1].remove(var)

# global scope object, each SCRIPT node pushes one more level on this
scope = Scope()

################################################################################
# code generation functions
################################################################################

def unit(a):
	va, vr, vlen = scope.alloc(), scope.alloc(), scope.alloc()
	r = [
		"%s = %s" % (va, o(a)),
		"%s = new Vector(0, 0)" % vr,
		"%s = Math.sqrt(%s.x*%s.x + %s.y*%s.y)" % (vlen, va, va, va, va),
		"%s.x = %s.x / %s" % (vr, va, vlen),
		"%s.y = %s.y / %s" % (vr, va, vlen),
		vr
	]
	scope.free(va), scope.free(vr), scope.free(vlen)
	return r

def normalize(a):
	va, vlen = scope.alloc(), scope.alloc()
	r = [
		"%s = %s" % (va, o(a)),
		"%s = Math.sqrt(%s.x*%s.x + %s.y*%s.y)" % (vlen, va, va, va, va),
		"%s.x /= %s" % (va, vlen),
		"%s.y /= %s" % (va, vlen)
	]
	scope.free(va), scope.free(vlen)
	return r

def simple_unary_to_num(func):
	def custom(a):
		va = scope.alloc()
		r = ["%s = %s" % (va, o(a))] + func(va)
		scope.free(va)
		return r
	return custom

def simple_unary_to_vec(func):
	def custom(a):
		va, vr = scope.alloc(), scope.alloc()
		r = [
			"%s = %s" % (va, o(a)),
			"%s = new Vector(0, 0)" % vr
			] + func(vr, va) + [
			vr
		]
		scope.free(va), scope.free(vr)
		return r
	return custom

def simple_binary_to_num(func):
	def custom(a, b):
		va, vb = scope.alloc(), scope.alloc()
		r = [
			"%s = %s" % (va, o(a)),
			"%s = %s" % (vb, o(b)),
			] + func(va, vb)
		scope.free(va), scope.free(vb)
		return r
	return custom

def simple_binary_to_vec(func):
	def custom(a, b):
		va, vb, vr = scope.alloc(), scope.alloc(), scope.alloc()
		r = [
			"%s = %s" % (va, o(a)),
			"%s = %s" % (vb, o(b)),
			"%s = new Vector(0, 0)" % vr
			] + func(vr, va, vb) + [
			vr
		]
		scope.free(va), scope.free(vb), scope.free(vr)
		return r
	return custom

def simple_inplace_binary_to_vec(func):
	def custom(a, b):
		va, vb = scope.alloc(), scope.alloc()
		r = [
			"%s = %s" % (va, o(a)),
			"%s = %s" % (vb, o(b)),
			] + func(va, vb)
		scope.free(va), scope.free(vb)
		return r
	return custom

def lerp(a, b, c):
	va, vb, vc = scope.alloc(), scope.alloc(), scope.alloc()
	r = [
		"%s = %s" % (va, o(a)),
		"%s = %s" % (vb, o(b)),
		"%s = %s" % (vc, o(c)),
		"%s + (%s - %s) * %s" % (va, vb, va, vc)
	]
	scope.free(va), scope.free(vb), scope.free(vc)
	return r

global_funcs = {
	"lerp": lerp
}

unary_funcs = {
	"unit": unit,
	"normalize": normalize,
	"neg": simple_unary_to_vec(lambda a, b: [
		"%s.x = -%s.x" % (a, b),
		"%s.y = -%s.y" % (a, b)
	]),
	"flip": simple_unary_to_vec(lambda a, b: [
		"%s.x = %s.y" % (a, b),
		"%s.y = -%s.x" % (a, b)
	]),
	"length": simple_unary_to_num(lambda a: [
		"Math.sqrt(%s.x*%s.x + %s.y*%s.y)" % (a, a, a, a)
	]),
	"lengthSquared": simple_unary_to_num(lambda a: [
		"%s.x*%s.x + %s.y*%s.y" % (a, a, a, a)
	]),
}

binary_funcs = {
	"add": simple_binary_to_vec(lambda a, b, c: [
		"%s.x = %s.x + %s.x" % (a, b, c),
		"%s.y = %s.y + %s.y" % (a, b, c)
	]),
	"sub": simple_binary_to_vec(lambda a, b, c: [
		"%s.x = %s.x - %s.x" % (a, b, c),
		"%s.y = %s.y - %s.y" % (a, b, c)
	]),
	"mul": simple_binary_to_vec(lambda a, b, c: [
		"%s.x = %s.x * %s" % (a, b, c),
		"%s.y = %s.y * %s" % (a, b, c)
	]),
	"div": simple_binary_to_vec(lambda a, b, c: [
		"%s.x = %s.x / %s" % (a, b, c),
		"%s.y = %s.y / %s" % (a, b, c)
	]),
	"minComponents": simple_binary_to_vec(lambda a, b, c: [
		"%s.x = Math.min(%s.x, %s.x)" % (a, b, c),
		"%s.y = Math.min(%s.y, %s.y)" % (a, b, c)
	]),
	"maxComponents": simple_binary_to_vec(lambda a, b, c: [
		"%s.x = Math.max(%s.x, %s.x)" % (a, b, c),
		"%s.y = Math.max(%s.y, %s.y)" % (a, b, c)
	]),
	"dot": simple_binary_to_num(lambda a, b: [
		"%s.x * %s.x + %s.y * %s.y" % (a, b, a, b)
	]),
	"inplaceAdd": simple_inplace_binary_to_vec(lambda a, b: [
		"%s.x += %s.x" % (a, b),
		"%s.y += %s.y" % (a, b)
	]),
	"inplaceSub": simple_inplace_binary_to_vec(lambda a, b: [
		"%s.x -= %s.x" % (a, b),
		"%s.y -= %s.y" % (a, b)
	]),
	"inplaceMul": simple_inplace_binary_to_vec(lambda a, b: [
		"%s.x *= %s" % (a, b),
		"%s.y *= %s" % (a, b)
	]),
	"inplaceDiv": simple_inplace_binary_to_vec(lambda a, b: [
		"%s.x /= %s" % (a, b),
		"%s.y /= %s" % (a, b)
	]),
}

################################################################################
# parse tree visitor
################################################################################

opmap = {
	# unary operands
	"NOT": "!",
	"VOID": "void",
	"UNARY_PLUS": "+",
	"UNARY_MINUS": "-",
	"BITWISE_NOT": "~",

	# binary operands
	"PLUS": "+",
	"LT": "<",
	"EQ": "==",
	"AND": "&&",
	"OR": "||",
	"MINUS": "-",
	"MUL": "*",
	"LE": "<=",
	"NE": "!=",
	"STRICT_EQ": "===",
	"DIV": "/",
	"GE": ">=",
	"INSTANCEOF": "instanceof",
	"IN": "in",
	"GT": ">",
	"BITWISE_OR": "|",
	"BITWISE_AND": "&",
	"BITWISE_XOR": "^",
	"STRICT_NE": "!==",
	"LSH": "<<",
	"RSH": ">>",
	"URSH": ">>>",
	"MOD": "%"
}

# interesting to know how many function calls got inlined
inline_count = 0

# modified from s-expr output example, just turns the parse tree back
# into javascript except specific function calls, which it inlines
# (sexp.py can be found at http://code.google.com/p/pynarcissus/)
def o(n, handledattrs=[]):
	global inline_count
	attrs_ = {}
	for attr in handledattrs:
		attrs_[attr] = True
	subnodes_ = []
	had_error = False
	def check(attrs=[], optattrs=[], subnodes=0):
		if not (type(attrs) == list and type(optattrs) == list and
				type(subnodes) == int):
			raise ProgrammerError, "Wrong arguments to check(...)!"
		for attr in attrs: attrs_[attr] = True
		for attr in optattrs:
			if hasattr(n, attr): attrs_[attr] = True
		for i in xrange(subnodes):
			subnodes_.append(True)
	try:
		check(attrs=["append", "count", "extend", "filename", "getSource",
					"indentLevel", "index", "insert", "lineno", "pop",
					"remove", "reverse", "sort", "tokenizer", "type", "type_"],
					optattrs=["end", "start", "value"])

		if n.type == "ARRAY_INIT":
			check(subnodes=len(n))
			return "[" + ", ".join(o(x) for x in n) + "]"

		elif n.type == "ASSIGN":
			check(subnodes=2)
			if getattr(n[0],"assignOp", None) is not None:
				return "%s %s= %s" % (o(n[0], handledattrs=["assignOp"]), jsparser.tokens[n[0].assignOp], o(n[1]))
			else:
				return "%s = %s" % (o(n[0], handledattrs=["assignOp"]), o(n[1]))

		elif n.type == "BLOCK":
			check(subnodes=len(n))
			return "{%s\n}" % "".join("\n" + o(x) for x in n)

		elif n.type in ("BREAK", "CONTINUE"):
			check(attrs=["target"], optattrs=["label"])
			if hasattr(n,"label"):
				return "%s %s" % (n.value, n.label)
			return n.value

		elif n.type == "CALL":
			check(subnodes=2)
			if n[0].type == "DOT" and n[0][1].type == "IDENTIFIER":
				# must pass n[0][0] and n[1] directly to unary_funcs[func] or binary_funcs[func]
				# because of required order of scope.alloc() and scope.free()
				func = o(n[0][1])
				if len(n[1]) == 0 and func in unary_funcs:
					inline_count += 1
					return "(%s)" % ", ".join(unary_funcs[func](n[0][0]))
				elif len(n[1]) == 1 and func in binary_funcs:
					inline_count += 1
					return "(%s)" % ", ".join(binary_funcs[func](n[0][0], n[1]))
			elif n[0].type == "IDENTIFIER":
				func = o(n[0])
				if func in global_funcs:
					inline_count += 1
					return "(%s)" % ", ".join(global_funcs[func](*n[1]))
			return "%s(%s)" % (o(n[0]), o(n[1]))

		elif n.type == "CASE":
			check(attrs=["caseLabel","statements"])
			return "case %s:%s" % (o(n.caseLabel), o(n.statements))

		elif n.type == "CATCH":
			check(attrs=["block","guard","varName"])
			return "catch (%s) %s" % (n.varName, o(n.block))

		elif n.type == "COMMA":
			check(subnodes=2)
			return "%s" % ", ".join("%s" % o(x) for x in n)

		elif n.type == "DEFAULT":
			check(attrs=["statements"])
			return "default: %s" % o(n.statements)

		elif n.type == "NEW":
			check(subnodes=1)
			return "new %s()" % o(n[0])

		elif n.type == "TYPEOF":
			check(subnodes=1)
			return "typeof %s " % o(n[0])

		elif n.type == "DELETE":
			check(subnodes=1)
			return "delete %s" % o(n[0])

		elif n.type in ("UNARY_MINUS", "NOT", "VOID", "BITWISE_NOT", "UNARY_PLUS"):
			check(subnodes=1)
			return "%s%s%s" % (opmap[n.type], " " if n.type == "VOID" else "", o(n[0]))

		elif n.type == "DO":
			check(attrs=["body", "condition", "isLoop"])
			assert n.isLoop
			return "do %s while (%s)" % (o(n.body), o(n.condition))

		elif n.type == "DOT":
			check(subnodes=2)
			return "%s.%s" % (o(n[0]), o(n[1]))

		elif n.type == "FUNCTION":
			check(attrs=["functionForm","params","body"],
					optattrs=["name"])
			if n.functionForm == 0:
				return "function %s(%s) {\n%s\n}" % (n.name, ", ".join(n.params), o(n.body))
			else:
				return "function(%s) {\n%s\n}" % (", ".join(n.params), o(n.body))

		elif n.type == "FOR":
			check(attrs=["body","setup","condition","update","isLoop"])
			assert n.isLoop
			setup = o(n.setup) if n.setup is not None else ""
			condition = o(n.condition) if n.condition is not None else ""
			update = o(n.update) if n.update is not None else ""
			body = o(n.body) if n.body is not None else ""
			return "for (%s; %s; %s) %s" % (setup, condition, update, body)

		elif n.type == "FOR_IN":
			check(attrs=["body","iterator","object","isLoop","varDecl"])
			assert n.isLoop
			s = "for ("
			if n.varDecl:
				assert n.varDecl.type == "VAR"
				assert len(n.varDecl) == 1
				assert n.varDecl[0].type == "IDENTIFIER"
				assert n.varDecl[0].value == n.iterator.value
				s += "var "
			return s + "%s in %s) %s" % (o(n.iterator), o(n.object), o(n.body))

		elif n.type == "GROUP":
			check(subnodes=1)
			return "(%s)" % o(n[0])

		elif n.type == "HOOK":
			check(subnodes=3)
			return "%s ? %s : %s" % (o(n[0]), o(n[1]), o(n[2]))

		elif n.type == "IDENTIFIER":
			check(optattrs=["initializer","name","readOnly"])
			if hasattr(n,"name"): assert n.name == n.value
			if hasattr(n,"initializer"):
				return "%s = %s" % (n.value, o(n.initializer))
			return str(n.value)

		elif n.type == "IF":
			check(attrs=["condition","thenPart","elsePart"])
			if n.elsePart:
				return "if (%s) %s else %s" % (o(n.condition), o(n.thenPart), o(n.elsePart))
			return "if (%s) %s" % (o(n.condition), o(n.thenPart))

		elif n.type in ("INCREMENT", "DECREMENT"):
			check(optattrs=["postfix"], subnodes=1)
			op = "++" if n.type == "INCREMENT" else "--"
			if getattr(n, "postfix", False):
				return "%s%s" % (o(n[0]), op)
			return "%s%s" % (op, o(n[0]))

		elif n.type == "INDEX":
			check(subnodes=2)
			return "%s[%s]" % (o(n[0]), o(n[1]))

		elif n.type == "LIST":
			check(subnodes=len(n))
			return ", ".join(o(x) for x in n)

		elif n.type == "NEW_WITH_ARGS":
			check(subnodes=2)
			return "%s %s(%s)" % (n.value, o(n[0]), o(n[1]))

		elif n.type in ("NUMBER", "TRUE", "FALSE", "THIS", "NULL"):
			return str(n.value)

		elif n.type == "OBJECT_INIT":
			check(subnodes=len(n))
			return "{%s\n}" % ",".join("\n" + o(x) for x in n)

		elif n.type in ("PLUS", "LT", "EQ", "AND", "OR", "MINUS", "MUL", "LE",
				"NE", "STRICT_EQ", "DIV", "GE", "INSTANCEOF", "IN", "GT",
				"BITWISE_OR", "BITWISE_AND", "BITWISE_XOR", "STRICT_NE", "LSH",
				"RSH", "URSH", "MOD"):
			check(subnodes=2)
			return "%s %s %s" % (o(n[0]), opmap[n.type], o(n[1]))

		elif n.type == "PROPERTY_INIT":
			check(subnodes=2)
			return "%s: %s" % (o(n[0]), o(n[1]))

		elif n.type == "REGEXP":
			return "/%s/%s" % (n.value["regexp"], n.value["modifiers"])

		elif n.type == "RETURN":
			if type(n.value) == str:
				return "return"
			return "return %s" % o(n.value)

		elif n.type == "SCRIPT":
			check(attrs=["funDecls","varDecls"], subnodes=len(n))
			scope.push()
			body = ""
			for x in n:
				body += o(x) + "\n"
			locals = scope.pop()
			if locals:
				return "var %s;\n%s" % (", ".join(locals), body)
			return body

		elif n.type == "SEMICOLON":
			check(attrs=["expression"])
			if not n.expression: return ";"
			return o(n.expression) + ";"

		elif n.type == "STRING":
			return repr(n.value)

		elif n.type == "SWITCH":
			check(attrs=["cases", "defaultIndex", "discriminant"])
			assert (n.defaultIndex == -1 or
					n.cases[n.defaultIndex].type == "DEFAULT")
			return "switch (%s) {\n%s\n}" % (o(n.discriminant), "\n".join(o(x) for x in n.cases))

		elif n.type == "THROW":
			check(attrs=["exception"])
			return "throw %s" % o(n.exception)

		elif n.type == "TRY":
			check(attrs=["catchClauses","tryBlock"], optattrs=["finallyBlock"])
			if hasattr(n,"finallyBlock"):
				return " ".join(["try " + o(n.tryBlock)] + [o(x) for x in n.catchClauses] + ["finally " + o(n.finallyBlock)])
			return "try %s" % " ".join([o(n.tryBlock)] + [o(x) for x in n.catchClauses])

		elif n.type in ("VAR", "CONST"):
			check(subnodes=len(n))
			return "var %s" % ", ".join(o(x) for x in n)

		elif n.type == "WHILE":
			check(attrs=["condition","body","isLoop"])
			assert n.isLoop
			return "while (%s) %s" % (o(n.condition), o(n.body))

		else:
			raise UnknownNode, "Unknown type %s" % n.type
	except Exception, e:
		had_error = True
		raise
	finally:
		if not had_error:
			realkeys = [x for x in dir(n) if x[:2] != "__"]
			for key in realkeys:
				if key not in attrs_:
					raise ProgrammerError, "key '%s' unchecked on node %s!" % (
							key, n.type)
			if len(realkeys) != len(attrs_):
				for key in attrs_:
					if key not in realkeys:
						raise ProgrammerError, ("key '%s' checked "
								"unnecessarily on node %s!" % (key, n.type))
			if len(subnodes_) != len(n):
				raise ProgrammerError, ("%d subnodes out of %d checked on node "
						"%s" % (len(subnodes_), len(n), n.type))

def js_inline(js):
	global inline_count
	inline_count = 0
	result = o(jsparser.parse(js))
	print "inlined %d function calls" % inline_count
	return result

if __name__ == "__main__":
	print js_inline(open("js_inline.test.js").read())