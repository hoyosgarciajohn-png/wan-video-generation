import { readFileSync, mkdirSync, writeFileSync } from "node:fs";
import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";
import standaloneCode from "ajv/dist/standalone/index.js";

const schema = JSON.parse(
  readFileSync(
    new URL("../../../contracts/bundle.schema.json", import.meta.url),
  ),
);
const ajv = new Ajv2020({ strict: false, code: { source: true } });
addFormats(ajv);
const validate = ajv.compile(schema);
const directory = new URL("../src/generated/", import.meta.url);
mkdirSync(directory, { recursive: true });
writeFileSync(
  new URL("bundle-validator.cjs", directory),
  "// Generated from contracts/bundle.schema.json; run npm run generate:validator.\n" +
    standaloneCode(ajv, validate) +
    "\n",
);
