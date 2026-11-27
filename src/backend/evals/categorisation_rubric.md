# Teacher rubric: categories of spending bookings

You label one Swiss bank customer's spending bookings (money out) with exactly one category each.
Judge every booking on its own: its text, payee, amount, weekday, channel and currency. Two bookings at
the same payee can get different categories (Migros groceries vs. a Migros garden chair; Coop vs. Coop
Pronto fuel). Use the persona file and the context only where a booking cannot be understood without it.

## Categories (the 13 the model may answer)

- **housing**: rent, mortgage interest paid to the bank, Nebenkosten, electricity, gas, heating, water,
  internet and TV at home (incl. Swisscom/Sunrise/Salt home internet), Serafe radio/TV fee, household
  repairs and caretaker, home contents bought for the flat are NOT housing (they are shopping).
- **groceries**: supermarkets (Migros, Coop, Denner, Aldi, Lidl, Volg, Spar), bakeries, butchers,
  markets, food shops, Coop Pronto / Migrolino shop purchases, foreign supermarkets.
- **loan_leasing**: instalments of a loan, a leasing contract or an instalment purchase (Ratenvertrag).
- **insurance**: insurance premiums: health insurance premium (Krankenkasse Prämie), household,
  liability, car, life, travel insurance.
- **health**: doctor, dentist, hospital, pharmacy, optician, therapy, health insurance excess and
  co-payment bills (Franchise, Selbstbehalt), also when the patient is a child.
- **transport**: public transport (SBB, ZVV, Bernmobil, Libero, tickets, GA, Halbtax), fuel (also at Coop
  Pronto/Migrolino petrol stations), parking, car service and tyres, vignette, taxi, Uber, bike shop
  repairs, e-scooters, car sharing.
- **restaurants**: restaurants, cafés, bars, canteens, take-away (Migros Take Away, SV Restaurant),
  food delivery, coffee to go, abroad as well.
- **shopping**: clothes, shoes, electronics, furniture, household goods, DIY, garden, books bought as
  goods, drugstore and cosmetics, online shops (Galaxus, Digitec, Zalando, Amazon), marketplaces
  (Ricardo, Tutti), gifts, hairdresser and personal care.
- **subscriptions_media**: recurring digital or media services: streaming (Netflix, Spotify, Disney+),
  software and cloud (Apple iCloud, Dropbox, Microsoft 365, Adobe), mobile phone plan, newspapers and
  magazines, app stores.
- **leisure_travel**: holidays, flights, hotels, holiday rentals, travel agencies, sport and fitness
  (gym membership, ski passes, climbing hall), culture (cinema, theatre, concerts, museums, tickets),
  hobbies, courses for adults, events.
- **taxes**: tax payments and advance payments to the Steueramt, church tax, dog tax.
- **children**: childcare (Kita, Hort, nanny), school fees and material, children's clothes and toys,
  children's activities and courses (swimming lessons, music school), pocket money, child allowances paid
  out. Health care for a child is health, not children.
- **other**: only when no category above fits: cash withdrawals (Bancomat), bank and card fees,
  donations, payments to private persons whose purpose the text does not say, fines, membership fees of
  associations without a clear category, unclear texts.

## Borders, decided

- Health insurance: the monthly premium is insurance; an excess or co-payment bill is health.
- Phone: mobile plan is subscriptions_media; home internet/TV is housing. A Swisscom booking goes by its
  text (Mobile/Natel vs. blue Internet/TV/Home); when the text does not say, pick by amount and channel
  and mark it `border`.
- Fitness and sport memberships are leisure_travel even when they recur monthly; subscriptions_media is
  only for digital/media services.
- Children vs. shopping: clothes, toys or school goods clearly for a child (Kinder, Spielwaren, Kids) are
  children; general shops are shopping.
- TWINT or transfers to a private person: other, unless the message names the purpose ("Znacht" is
  restaurants, "Geschenk" is shopping, "Miete" is housing).
- Restaurants vs. groceries at the same chain: Take Away, Restaurant or canteen is restaurants; the shop
  is groceries.
- A foreign card purchase is categorised by what was bought, not by being abroad: a hotel abroad is
  leisure_travel, a restaurant abroad is restaurants, a supermarket abroad is groceries.
- Use other honestly: when a text is too cryptic to tell, other is the right answer; mark it `cryptic`.

## Output per booking

One line of JSON: `{"uid": ..., "category": ..., "reason": "<one short line>", "hard": [...]}`.
`hard` lists any of: `multi_payee` (this payee's bookings fall into more than one category and this one
needs care), `foreign` (card purchase abroad or in a foreign currency), `cryptic` (short or unclear
text), `needs_context` (only understandable with the standing orders, documents or persona),
`border` (sits on one of the borders above). Empty list when easy.

## Decided after labelling, before any model run

- TWINT «Grill» (a share of a barbecue): groceries. «Elternabend Apéro»: restaurants. «Fussballturnier»
  in a family with a child playing football: children.
- Strassenverkehrsamt: a bill that says Verkehrsabgaben is taxes (vehicle tax); an unexplained card
  payment at the office is transport (inspection). Both `border`.
