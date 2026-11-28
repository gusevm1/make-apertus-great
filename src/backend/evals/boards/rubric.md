# Rubric: is this a board Maxim would show in the demo?

Written before the first judged run. A board is acceptable only when every
deterministic check and every judged criterion passes.

## Deterministic checks (in code, `run.py`)

- **resolved**: every tile resolves against the banking API now, and no
  title names a figure its payload does not hold.
- **hero_fits**: the first tile of the first board shows one of the three
  strongest signals whose template can carry a headline (first boards only).
- **no_repeats**: no tile (template and arguments) appears twice, on one
  board or across boards.
- **tile_count**: the main board has 5 to 7 tiles, a second board 3 to 5, a
  board made for a request 2 to 5.
- **names_short** (added after the first live Apertus boards): every board
  name is a tab label, one to three words, at most 24 characters, no question
  mark.
- **titles_short** (same): every tile title is at most 28 characters and has
  none of the filler words upcoming, expected, overview, progress, late,
  total, current, trend, breakdown.
- **differs**: no other customer's main board in the same run has the same
  templates in the same order.

## Judged criteria (GLM through the cache)

The judge reads this rubric, the persona's Markdown file as the truth about
the customer's life, and the board with its resolved figures.

- **hero_question**: the first tile answers the question this customer
  actually has, as the persona describes it.
- **about_customer**: every tile is about this customer's real situation;
  none is generic filler or belongs to another kind of customer.
- **titles**: titles are short, read like a person wrote them, use the
  customer's terms, and match what the tile shows.
- **not_empty_or_repeated**: no tile is empty, zero or pointless, and no two
  tiles show the same thing in different words.
- **coherent**: the board as a whole tells one story a customer would follow;
  a second board, when there is one, is about one theme of this life.

## Ground truth from the brief (added after run 1)

The brief (`docs/night-run-boards.md`) and the confirmed mockups fix two heroes,
and the judge reads them as part of the truth about the customer:

- Daniela needs to know whether her money lasts until payday: the hero is
  what is left on the day before her salary.
- Lukas needs an overview of what he owns and where it goes: the hero is what
  he owns (net worth), with where the money goes beside it.
- A single bill that carries a reminder may stand beside the list of bills it
  is in, to show its detail; the confirmed Daniela board does this with the
  dentist's second reminder.

## A board made for a request (added with the request runs)

The customer asked for one board in their own words. The same criteria hold,
read against the request:

- **hero_question**: the first tile answers the request most directly.
- **about_customer**: every tile is about the request and this customer's real
  situation; a strong signal that is not about the request does not belong.
- **coherent**: the board is about the request and nothing else.
- A small board (two tiles) passes when the data holds nothing more about the
  request; an off-topic tile added to fill it fails.
