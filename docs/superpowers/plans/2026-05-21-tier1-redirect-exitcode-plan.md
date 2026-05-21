# Tier 1 Bugfix Planı — Redirect & Exit Kodu

> Kapsam: Kishi-Shell v2.0.0.3'te **scripting'i kurtaran 4 bug**. Hepsi reprodüksiyonla doğrulandı (2026-05-21).
> Çapraz platform (Linux + Windows) hedeflenir. Yöntem: builtin/function çıktısı için **`contextlib.redirect_stdout/redirect_stderr`** (saf Python, OS-bağımsız).
> Her faz ayrı bir oturumda çalıştırılabilir. Önce TDD (kırmızı test), sonra düzeltme.

---

## Phase 0 — Bulgular & İzin Verilen API'ler (ALWAYS FIRST)

### Kaynaklar (okundu + reprodüksiyon yapıldı, bu oturum)
- `kishi/executor.py` — tamamı okundu; `execute_pipeline` (sat. 21-282), `process_command_line` (sat. 388-428).
- `kishi/main.py` — `_main_inner` `-c` dalı (sat. 207-213), non-interactive dal (sat. 219-230).
- `kishi/builtins.py` — `kishi_exit` (sat. 40-42).
- `kishi/tui_dashboard.py` — **kopyalanacak desen**: `_run_builtin`/`_run_function` `contextlib.redirect_stdout` kullanımı (sat. 430-453).
- `kishi/expander.py` — `Expander.expand(arg_list, globbing=True)` imzası (sat. 7-8); `globbing=False` tilde+değişkeni açar, glob'u açmaz.
- `tests/test_executor.py` — `clean_state` fixture (sat. 22-41), `_make_pipeline` helper (sat. 44-52), `TestProcessCommandLine` (sat. 632-649).
- `tests/test_builtins.py` — `capsys`/`tmp_path` desenleri, `kishi_pwd` çıktısı testi (sat. 95-101).

### Reprodüksiyonla kanıtlanan kusurlar
- **#1**: `process_command_line('false')` → `None` döndü → `kishi -c` daima exit 0.
- **#2**: `kishi_exit` daima `sys.exit(0)`, `args` yok sayılır.
- **#3**: `pwd > f` → `/tmp` ekrana yazıldı, `f` oluşmadı (builtin redirect uygulanmıyor).
- **#4**: `echo viavar > $MYOUT` → literal `$MYOUT` dosyası oluştu (hedef expand edilmiyor).

### İzin verilen API'ler (var olduğu doğrulanmış)
- `contextlib.redirect_stdout(fileobj)`, `contextlib.redirect_stderr(fileobj)` — Python stdlib, Linux+Windows aynı. (`tui_dashboard.py:432` zaten kullanıyor.)
- `open(path, 'w'|'a', encoding=...)` — dosya nesnesi; contextlib'e geçilir.
- `Expander.expand([target], globbing=False)` — mevcut imza.
- `os.open(...)` + `os.O_*` flag'leri — external/fork yolunda zaten kullanılıyor (`executor.py:162-170`).
- `sys.exit(int)` — SystemExit `main()` tarafından `except SystemExit: raise` ile yayılır (`main.py:285-286`).

### Anti-pattern'ler (YAPMA)
- ❌ fd-level `os.dup2` ile builtin redirect (Windows'ta flush/restore riski — kullanıcı çapraz-platform sorunsuzluğu istedi).
- ❌ `process_command_line`'ın imzasını/parametrelerini değiştirmek (sadece `return` ekle).
- ❌ Var olmayan `Expander.expand_target()` gibi metot uydurmak — sadece mevcut `expand`'i kullan.
- ❌ Redirect yokken builtin çağrı yolunu değiştirmek (mevcut testleri bozar).

---

## Phase 1 — Kırmızı Testler (TDD önce)

**Ne yapılacak:** `tests/test_executor.py`'a yeni test sınıfları ekle. Önce ÇALIŞTIR, KIRMIZI olduklarını gör.

`_make_pipeline` helper'ı redirect alanlarını set edecek şekilde genişlet (yeni bir yardımcı, mevcut imzayı bozmadan):
```python
def _make_redirect_pipeline(args, out_file=None, out_append=False,
                            err_file=None, in_file=None, err_to_out=False):
    pipe = PipelineNode()
    cmd = CommandNode()
    cmd.args = list(args)
    cmd.out_file = out_file; cmd.out_append = out_append
    cmd.err_file = err_file; cmd.in_file = in_file; cmd.err_to_out = err_to_out
    pipe.commands.append(cmd)
    return pipe
```

Eklenecek testler:
- **#3** `TestBuiltinRedirection`:
  - `pwd > f` (tmp_path) → dosya cwd içerir, **stdout boş** (`capsys`).
  - `pwd >> f` → append modu (iki çağrı → iki satır).
  - builtin `2>` ile stderr'e yazan mock builtin → err dosyasına yazar.
  - function redirect: `state.FUNCTIONS['x']` body `pwd` → `x > f` dosyaya yazar.
  - **Regresyon:** redirect'siz builtin (mevcut `_make_pipeline`) hâlâ doğrudan çağrılır, dönüş kodu korunur.
- **#4** `TestRedirectTargetExpansion`:
  - `out_file="$MYVAR"` (MYVAR=/tmp/x) → gerçek `/tmp/x` yazılır, literal `$MYVAR` dosyası OLUŞMAZ.
  - `out_file="~/..."` → `os.path.expanduser` hedefi.
- **#1** `TestProcessCommandLineExitCode`:
  - `process_command_line("false")` → `1` döndürür (mock builtin `_false`→1 ile, ya da gerçek `false` external).
  - `process_command_line("true")` → `0`.
- **#2** `TestExitBuiltin`:
  - `kishi_exit(["exit","5"])` → `SystemExit` kodu `5` (pytest.raises(SystemExit) + `e.value.code == 5`).
  - `kishi_exit(["exit"])` → kod `0`.

**Doğrulama:** `python -m pytest tests/test_executor.py -k "Redirection or ExitCode or ExitBuiltin or Expansion" -v` → hepsi **FAIL/ERROR** (henüz fix yok).

**Anti-pattern guard:** Testler gerçek davranışı (dosya içeriği, exit kodu, capsys çıktısı) doğrulasın; sadece "çağrıldı mı" değil.

---

## Phase 2 — Fix #4: Redirect hedef expansion (en küçük, en düşük risk)

**Ne yapılacak:** `execute_pipeline` içinde `valid_commands` kurulurken (mevcut `executor.py:28-35` döngüsü), `cmd.args` expand edildikten **sonra** redirect hedeflerini de expand et:
```python
for cmd in commands:
    if cmd.args and cmd.args[0] in ALIASES:
        ...
    cmd.args = Expander.expand(cmd.args)
    # YENİ: redirect hedeflerini de genişlet (tilde + $VAR; glob yok)
    for attr in ("in_file", "out_file", "err_file"):
        val = getattr(cmd, attr)
        if val:
            exp = Expander.expand([val], globbing=False)
            if exp:
                setattr(cmd, attr, exp[0])
    if cmd.args:
        valid_commands.append(cmd)
```

**Neden burada:** Bu döngü hem builtin hem external hem Windows hem fork yolundan ÖNCE çalışır → tek değişiklik tüm yolları kapsar.

**Doğrulama:** Phase 1'deki `TestRedirectTargetExpansion` testleri **GEÇER**. `python -m pytest tests/test_executor.py -k Expansion -v`.

**Anti-pattern guard:** `globbing=True` KULLANMA (redirect hedefi glob'lanmamalı; çoklu eşleşme ambiguity'si). Tek elemanlı liste döner.

---

## Phase 3 — Fix #3: Builtin/function redirect (contextlib)

**Ne yapılacak:** `execute_pipeline` tek-komut yolunda (`executor.py:42-80`), builtin/function çağrısını redirect varsa bir yardımcıdan geçir. `tui_dashboard.py:430-453` desenini KOPYALA.

Yeni modül-seviyesi yardımcı (`executor.py`):
```python
import contextlib

def _run_redirected(callable_fn, call_args, cmd):
    """Builtin/function'ı stdout/stderr redirect uygulayarak çalıştır.
    contextlib kullanır — saf Python, Linux+Windows aynı."""
    has_redir = cmd.out_file or cmd.err_file or cmd.err_to_out
    if not has_redir:
        return callable_fn(call_args)

    out_ctx = contextlib.nullcontext()
    err_ctx = contextlib.nullcontext()
    out_fh = err_fh = None
    try:
        if cmd.out_file:
            out_fh = open(cmd.out_file, "a" if cmd.out_append else "w", encoding="utf-8")
            out_ctx = contextlib.redirect_stdout(out_fh)
        if cmd.err_to_out:
            # 2>&1: stderr'i mevcut (yönlendirilmiş) stdout'a bağla
            err_ctx = contextlib.redirect_stderr(out_fh if out_fh else sys.stdout)
        elif cmd.err_file:
            err_fh = open(cmd.err_file, "a" if cmd.err_append else "w", encoding="utf-8")
            err_ctx = contextlib.redirect_stderr(err_fh)
        with out_ctx, err_ctx:
            try:
                return callable_fn(call_args)
            except SystemExit:
                raise
    finally:
        if out_fh: out_fh.close()
        if err_fh: err_fh.close()
```

Tek-komut builtin dalı (`executor.py:65-66`):
```python
if cmd_name in BUILTINS:
    return _run_redirected(BUILTINS[cmd_name], cmd.args[actual_cmd_idx:], cmd)
```
Function dalı (`executor.py:67-80`): aynı şekilde, `execute_ast(FUNCTIONS[cmd_name])`'i `lambda _: execute_ast(...)` ile sarıp `_run_redirected`'tan geçir (positional param set/restore mantığı korunur).

**Doğrulama:** Phase 1'deki `TestBuiltinRedirection` **GEÇER**; mevcut `TestBuiltinDispatch`/`TestFunctionDefinitionAndCall` testleri **HÂLÂ GEÇER** (redirect'siz yol değişmedi). `python -m pytest tests/test_executor.py -v`.

**Anti-pattern guard:** ❌ `os.dup2` kullanma. ❌ `print()` çıktısını manuel string'e toplayıp tekrar yazma (contextlib zaten yakalar). ❌ `SystemExit`'i yutma (exit builtin'i çalışmalı) — `finally` ile dosya kapanır, exception yayılır.

---

## Phase 4 — Fix #1: process_command_line exit kodu döndürsün

**Ne yapılacak:** `executor.py:426-428` — `execute_ast` sonucunu döndür:
```python
ast = Parser.parse(tokens)
if ast:
    return execute_ast(ast)
return 0
```
(Fonksiyon başındaki erken `return` yolları da `return 0` döndürsün — şu an boş `return` → `None`. `if not tokens: return 0` yap.)

`main.py` `-c` dalı (sat. 207-213) zaten `sys.exit(result or 0)` yapıyor → otomatik düzelir. **Ek:** non-interactive dalda (sat. 219-230) son komutun statüsünü izle:
```python
last = 0
for line in sys.stdin:
    line = line.strip()
    if line:
        last = process_command_line(line) or 0
sys.exit(last)
```

**Doğrulama:** `TestProcessCommandLineExitCode` **GEÇER**. Manuel: `python -m kishi -c "false"; echo $?` → `1`; `python -m kishi -c "true"; echo $?` → `0`. Mevcut `TestProcessCommandLine` testleri (dönüşü kontrol etmiyor) **HÂLÂ GEÇER**.

**Anti-pattern guard:** ❌ `process_command_line`'a yeni parametre ekleme. Sadece `return` davranışı değişir.

---

## Phase 5 — Fix #2: `exit N` çıkış kodunu onurlandırsın

**Ne yapılacak:** `builtins.py:40-42` `kishi_exit`:
```python
def kishi_exit(args):
    code = 0
    if len(args) > 1:
        try: code = int(args[1])
        except ValueError: code = 1
    print(f"\n{COLOR_AMBER}Kishi:{COLOR_RESET} Exiting safely. Goodbye!", file=sys.stderr)
    sys.exit(code)
```
(Çıkış mesajını `stderr`'e al ki `exit 0` redirect'te stdout'u kirletmesin — opsiyonel ama temiz.)

**Doğrulama:** `TestExitBuiltin` **GEÇER**. Manuel: `python -m kishi -c "exit 7"; echo $?` → `7`.

**Anti-pattern guard:** ❌ Geçersiz arg'da çökme — `ValueError`'da kod `1` (bash davranışı).

---

## Phase 6 — Doğrulama (Final)

1. **Tüm test paketi:** `python -m pytest tests/ -v` → **228 + yeni testler** hepsi yeşil, regresyon yok.
2. **Manuel uçtan uca** (yeni terminalde):
   - `python -m kishi -c "pwd > /tmp/v.txt"; cat /tmp/v.txt` → cwd dosyada.
   - `python -m kishi -c "echo a > /tmp/v2.txt && pwd >> /tmp/v2.txt"` → iki satır.
   - `python -m kishi -c "false"; echo $?` → `1`.
   - `python -m kishi -c "exit 5"; echo $?` → `5`.
   - `export D=/tmp; python -m kishi -c "pwd > \$D/v3.txt"` → `/tmp/v3.txt` yazılır.
3. **Anti-pattern grep guard'ları:**
   - `grep -n "os.dup2" kishi/executor.py` → builtin redirect bölgesinde OLMAMALI.
   - `grep -n "return execute_ast" kishi/executor.py` → `process_command_line` içinde VAR olmalı.
   - `grep -n "contextlib" kishi/executor.py` → VAR olmalı.
4. **CI:** `pyproject.toml testpaths=["tests"]` → kök `test_cursor*.py` toplanmaz; etkilenmez.
5. **Cross-platform notu:** contextlib + `open()` saf Python; Windows fark gerektirmez. `kishi_exit`/`process_command_line` platform-bağımsız.

---

## Etkilenen Dosyalar (özet)
- `kishi/executor.py` — Phase 2, 3, 4 (`_run_redirected` ekle, valid_commands döngüsü, process_command_line return).
- `kishi/builtins.py` — Phase 5 (`kishi_exit`).
- `kishi/main.py` — Phase 4 (non-interactive son statü).
- `tests/test_executor.py` — Phase 1 (yeni test sınıfları + helper).

## Riskler
- 🟢 Düşük. Tüm değişiklikler "redirect varsa yeni yol, yoksa eski yol" prensibiyle additive; mevcut 228 test kontrol noktası.
- ⚠️ `2>&1` sıralama semantiği bash ile tam eşleşmeyebilir (Tier 1 kapsamı dışı; ayrı not).
