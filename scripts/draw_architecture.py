"""Render the deployed Evidra architecture as hand-drawn SVG presentation boards."""

from html import escape
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "docs/architecture"
INK, BLUE, AMBER = "#ddd9ce", "#80b8cc", "#d9b16a"


class Board:
    def __init__(self, title, subtitle):
        self.parts = [
            '<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="850" viewBox="0 0 1600 850">',
            '<rect width="1600" height="850" fill="#151617"/>',
            '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M1 1L9 5L1 9" fill="none" stroke="context-stroke" stroke-width="1.3"/></marker></defs>',
        ]
        self.text(40, 45, title, 30)
        self.text(40, 78, subtitle, 16, BLUE)

    def text(self, x, y, lines, size=18, color=INK, anchor="start"):
        if isinstance(lines, str):
            lines = lines.split("\n")
        self.parts.append(
            f'<text x="{x}" y="{y}" fill="{color}" font-family="Comic Sans MS, Comic Sans, cursive" font-size="{size}" text-anchor="{anchor}">'
        )
        for i, line in enumerate(lines):
            self.parts.append(
                f'<tspan x="{x}" dy="{0 if i == 0 else size * 1.4}">{escape(line)}</tspan>'
            )
        self.parts.append("</text>")

    def frame(self, x, y, w, h, title, color=INK):
        self.parts.append(
            f'<path d="M{x} {y+3}L{x+w} {y}L{x+w-2} {y+h}L{x+2} {y+h-2}Z" fill="none" stroke="{color}" stroke-width="1.2" stroke-dasharray="7 7"/>'
        )
        self.text(x + 12, y + 25, title, 17, color)

    def node(self, x, y, w, h, lines, color=INK, size=18):
        self.parts.append(
            f'<path d="M{x+12} {y+1}Q{x-1} {y} {x+1} {y+14}L{x} {y+h-12}Q{x} {y+h+1} {x+13} {y+h}L{x+w-12} {y+h-1}Q{x+w+1} {y+h} {x+w} {y+h-13}L{x+w-1} {y+13}Q{x+w} {y} {x+w-13} {y}Z" fill="#151617" stroke="{color}" stroke-width="1.4"/>'
        )
        n = len(lines.split("\n"))
        self.text(
            x + w / 2,
            y + h / 2 - (n - 1) * size * 0.7 + size * 0.35,
            lines,
            size,
            color,
            "middle",
        )

    def cylinder(self, x, y, w, h, lines):
        self.parts.append(
            f'<path d="M{x} {y+14}C{x} {y-5} {x+w} {y-5} {x+w} {y+14}L{x+w} {y+h-14}C{x+w} {y+h+5} {x} {y+h+5} {x} {y+h-14}Z M{x} {y+14}C{x} {y+33} {x+w} {y+33} {x+w} {y+14}" fill="none" stroke="{INK}" stroke-width="1.3"/>'
        )
        self.text(x + w / 2, y + 49, lines, 16, INK, "middle")

    def arrow(self, points, label=None, at=None, color=INK, dashed=False):
        path = "M" + "L".join(f"{x},{y}" for x, y in points)
        dash = ' stroke-dasharray="6 6"' if dashed else ""
        self.parts.append(
            f'<path d="{path}" fill="none" stroke="{color}" stroke-width="1.3" marker-end="url(#arrow)"{dash}/>'
        )
        if label and at:
            self.text(*at, label, 14, color)

    def save(self, name):
        self.text(
            40,
            810,
            "Code baseline: main / 0d1888f  |  rshalvi/evidra  |  deployed design, not a future architecture",
            15,
            BLUE,
        )
        self.parts.append("</svg>")
        (OUT / name).write_text("\n".join(self.parts), encoding="utf-8")


def lld():
    b = Board(
        "evidra / your document, now with a voice",
        "one product flow — read the document first, then answer from its contents",
    )
    b.frame(35, 125, 1530, 235, "1 / prepare your document once")
    b.node(70, 200, 260, 100, "Upload a document\nPDF / image / TXT / MD", size=23)
    b.node(470, 200, 290, 100, "Read its text\npypdf or Tesseract OCR", size=23)
    b.node(900, 200, 285, 100, "Make it searchable\nPassages + E5 embeddings", size=23)
    b.cylinder(1320, 185, 200, 135, "Your workspace\nSQLite\nText + search vectors")
    b.arrow([(330, 250), (470, 250)])
    b.arrow([(760, 250), (900, 250)])
    b.arrow([(1185, 250), (1320, 250)])
    b.frame(35, 440, 1530, 210, "2 / ask a question — repeat for every voice turn")
    steps = [
        ("Speak or type\nEnglish / Hindi", INK),
        ("Turn voice into text\nWhisper / CPU", INK),
        ("Find source passages\nE5 + BM25 + MiniLM", INK),
        ("Write + check answer\nQwen3-4B / GPU", AMBER),
        ("Turn answer into voice\nPiper / CPU", INK),
        ("Listen + verify\nOriginal source shown", BLUE),
    ]
    xs = [65, 315, 565, 815, 1065, 1315]
    for x, (label, color) in zip(xs, steps):
        b.node(x, 510, 210, 100, label, color, 19)
    for x, z in zip(xs, xs[1:]):
        b.arrow([(x + 210, 560), (z, 560)])
    b.arrow(
        [(1370, 320), (1370, 390), (670, 390), (670, 510)],
        "retrieve evidence from your document",
        (720, 381),
        BLUE,
        True,
    )
    b.arrow(
        [(920, 510), (920, 415), (1470, 415), (1470, 320)],
        "save answer + source references",
        (1010, 408),
        BLUE,
        True,
    )
    b.text(
        65,
        690,
        "Hindi: translate question to English for search, then translate the checked answer back to Hindi (NLLB).",
        19,
        BLUE,
    )
    b.text(
        65,
        730,
        "If evidence is insufficient or checks fail, we withhold the draft and explain why. OCR and answers can still be imperfect.",
        18,
    )
    b.text(
        65,
        770,
        "Today: turn-taking, no streaming, shared HF GPU queue. Each visitor has a separate temporary workspace.",
        18,
        AMBER,
    )
    b.save("evidra-flow.svg")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    lld()
    print("Created the Evidra product flow SVG")
