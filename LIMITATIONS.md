# Limitations

What address-normalizer does not do, or does poorly. Read this before trusting a cleaned file.

## It does not check that an address exists

- **No geocoding and no USPS lookup.** Everything runs offline with rules and tables. A clean-looking
  address for a street that does not exist comes out clean. Use a CASS-certified service if mail
  must be deliverable.
- **ZIP and state are only checked against each other by first digit.** A ZIP in the wrong town of
  the right state passes. ZIP+4 is never checked.
- **City names are not checked or spelled.** `Sprngfield` stays `SPRNGFIELD`.

## Parsing

- **Rows without commas are split by rules.** The street ends at a unit (`Apt 4`), a PO box number
  or a street suffix. When the city also has a suffix word in it (`Lake Bramley`, `Park City`), the
  split is ambiguous and the row goes to review. Adding commas fixes it.
- **A spelled-out direction after the suffix, in a row without commas, is read as part of the
  city.** `12 Elm Rd North Ashby` gives city `NORTH ASHBY`, because real cities like that exist.
  With a comma, or with `N`, it is read as a post-directional. This is the main error in the
  benchmark.
- **Streets with no suffix** (`Broadway`) work only when commas separate the city.
- **Not handled:** rural routes (`RR 2 Box 5`), highway contract routes, military addresses
  (APO/FPO/DPO), Puerto Rico urbanizations, fractional house numbers (`12 1/2`) and two addresses
  in one cell. A street really named `Oak Park` with no suffix is read as street `OAK`, suffix
  `PARK`.
- **Numbered street names are kept as written.** `5th` and `Fifth` stay different.
- **Unit designators are kept as written.** `Apt 4` and `# 4` stay `APT 4` and `# 4` in the output,
  but match as duplicates because only the unit number is compared.
- **Output is upper case**, as in USPS Publication 28. There is no title-case option yet.
- **The suffix table is a subset** of Publication 28 appendix C1 (about 80 suffixes and their
  common misspellings), not the full list.

## Duplicates

- Two rows are duplicates only when every parsed field matches after cleaning (number, directions,
  street, suffix, unit number, PO box, and ZIP, or city and state when there is no ZIP). There is
  no fuzzy matching, so a typo in the street name splits a group.
- Rows sent to review are never put in a duplicate group.

## Benchmark

- The benchmark data is generated, so it only holds the kinds of mess the generator writes. The
  numbers in [BENCHMARK.md](BENCHMARK.md) are an upper bound for messy real files.
