import os
import sys

while True:
	komut = input("kishi$ - ")
	args = komut.split()

	if not args:
		continue

	pid = os.fork()
	if pid == 0:
		try:
			os.execvp(args[0], args)
		except FileNotFoundError:
			print(f"kishi$ - {args[0]}: command not found!")
			sys.exit(1)
	else:
		os.waitpid(pid,0) 
