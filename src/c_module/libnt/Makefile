LIBNT_SRC = libnt.c mman.c fnmatch.c
LIBNT_OBJS = $(patsubst %.c,$(OBJ)/nt/%.o,$(LIBNT_SRC))

all: $(LIB)/libnt.a $(OUT)/test$(BIN_EXT)

$(LIB)/libnt.a: $(LIBNT_OBJS)
	@$(MKDIR) -p `dirname $@`
	@echo -e "  AR\t    `basename $@`"
	@$(AR) $(ARFLAGS) $@ $^

$(OUT)/test.exe: $(OBJ)/nt/test.o $(LIB)/libnt.a
	@$(MKDIR) -p `dirname $@`
	@echo -e "  LD\t    `basename $@`"
	@$(CC) $(CFLAGS) $^ -o $@ -static $(LDFLAGS) $(LIBS) $(BIN_RES)

$(OBJ)/nt/%.o: %.c
	@$(MKDIR) -p `dirname $@`
	@echo -e "  CC\t    `basename $@`"
	@$(CC) $(CFLAGS) -c $< -o $@