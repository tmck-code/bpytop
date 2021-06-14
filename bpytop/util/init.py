from typing import List

class Init:
    running: bool = True
    initbg_colors: List[str] = []
    initbg_data: List[int]
    initbg_up: Graph
    initbg_down: Graph
    resized = False

    @classmethod
    def start(cls):
        Draw.buffer("init", z=1)
        Draw.buffer("initbg", z=10)
        for i in range(51):
            for _ in range(2):
                cls.initbg_colors.append(Color.fg(i, i, i))
        Draw.buffer(
            "banner",
            (
                f"{Banner.draw(Term.height // 2 - 10, center=True)}{Mv.d(1)}{Mv.l(11)}{Colors.black_bg}{Colors.default}"
                f'{Fx.b}{Fx.i}Version: {VERSION}{Fx.ui}{Fx.ub}{Term.bg}{Term.fg}{Color.fg("#50")}'
            ),
            z=2,
        )
        for _i in range(7):
            perc = f'{str(round((_i + 1) * 14 + 2)) + "%":>5}'
            Draw.buffer(
                "+banner",
                f"{Mv.to(Term.height // 2 - 2 + _i, Term.width // 2 - 28)}{Fx.trans(perc)}{Symbol.v_line}",
            )

        Draw.out("banner")
        Draw.buffer(
            "+init!",
            f'{Color.fg("#cc")}{Fx.b}{Mv.to(Term.height // 2 - 2, Term.width // 2 - 21)}{Mv.save}',
        )

        cls.initbg_data = [randint(0, 100) for _ in range(Term.width * 2)]
        cls.initbg_up = Graph(
            Term.width,
            Term.height // 2,
            cls.initbg_colors,
            cls.initbg_data,
            invert=True,
        )
        cls.initbg_down = Graph(
            Term.width,
            Term.height // 2,
            cls.initbg_colors,
            cls.initbg_data,
            invert=False,
        )

    @classmethod
    def success(cls):
        if not CONFIG.show_init or cls.resized:
            return
        cls.draw_bg(5)
        Draw.buffer(
            "+init!", f"{Mv.restore}{Symbol.ok}\n{Mv.r(Term.width // 2 - 22)}{Mv.save}"
        )

    @staticmethod
    def fail(err):
        if CONFIG.show_init:
            Draw.buffer("+init!", f"{Mv.restore}{Symbol.fail}")
            sleep(2)
        errlog.exception(f"{err}")
        clean_quit(
            1,
            errmsg=f"Error during init! See {CONFIG_DIR}/error.log for more information.",
        )

    @classmethod
    def draw_bg(cls, times: int = 5):
        for _ in range(times):
            sleep(0.05)
            x = randint(0, 100)
            Draw.buffer(
                "initbg",
                f"{Fx.ub}{Mv.to(0, 0)}{cls.initbg_up(x)}{Mv.to(Term.height // 2, 0)}{cls.initbg_down(x)}",
            )
            Draw.out("initbg", "banner", "init")

    @classmethod
    def done(cls):
        cls.running = False
        if not CONFIG.show_init:
            return
        if cls.resized:
            Draw.now(Term.clear)
        else:
            cls.draw_bg(10)
        Draw.clear("initbg", "banner", "init", saved=True)
        if cls.resized:
            return
        del cls.initbg_up, cls.initbg_down, cls.initbg_data, cls.initbg_colors
