window.DEMO = {
  repo: "address-normalizer",
  title: "address-normalizer",
  tagline: "Drop in a CSV or Excel file of messy US addresses. Get them in USPS Publication 28 form, split into fields, with unparseable rows sent to review and duplicates grouped.",
  pkg: "address_normalizer",
  packages: ["openpyxl"],
  inputs: [
    { id: "input", label: "Addresses (CSV or XLSX)", accept: ".csv,.xlsx,.xlsm,.txt,.tsv", sample: "samples/messy.csv" },
  ],
  options: [
    { id: "column", label: "One-line address column", type: "text", value: "address" },
    { id: "street", label: "or Street column", type: "text", value: "", placeholder: "Street" },
    { id: "city", label: "City", type: "text", value: "", placeholder: "City" },
    { id: "state", label: "State", type: "text", value: "", placeholder: "State" },
    { id: "zip", label: "ZIP", type: "text", value: "", placeholder: "Zip" },
  ],
  sampleNote: 'The sample is <a href="samples/messy.csv">messy.csv</a>: 46 rows of invented addresses, some written two or three ways, plus one broken row. For split columns, clear the one-line box and fill in Street, City, State and ZIP.',
  python: `
from pathlib import Path
from address_normalizer.cli import main as cli_main

def run(paths, opts):
    src = paths["input"][0]
    out = "/work/" + Path(src).stem + "-clean.xlsx"
    argv = ["clean", src, "-o", out]
    if opts.get("street", "").strip():
        for k in ("street", "city", "state", "zip"):
            if opts.get(k, "").strip():
                argv += ["--" + k, opts[k].strip()]
    else:
        argv += ["--column", opts.get("column", "").strip() or "address"]
    code, log = run_cli(cli_main, argv)
    if code != 0 or not Path(out).exists():
        return {"ok": False, "log": log, "sheets": [], "download": None}
    return {"ok": True, "log": log, "sheets": sheets_from_xlsx(out), "download": out}
`,
};
