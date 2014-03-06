
all: z80.py

z80.py: z80th.py z80bh.py
	cat z80th.py > z80.py
	cat z80bh.py >> z80.py

z80bh.py: z80gen.py
	python ./z80gen.py -o $@

clean:
	-rm *.pyc
	-rm z80bh.py
	-rm z80.py
