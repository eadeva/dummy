"use strict";
// A small protocol fixture. Production never imports this catalogue.
const contexts = ["vars", "default", "environment", "job", "step", "secret", "destination"];
const entries = [
  { reference: "git.short_commit", group: "Git", description: "Short source commit.", contexts },
  { reference: "run.bin_dir", group: "Run", description: "Binary directory.", contexts: ["vars", "job", "step", "secret"] },
  { reference: "env:NAME", group: "Environment", description: "Environment variable name.", contexts, placeholder: "NAME" },
  { reference: "env:PATH", group: "Environment", description: "Environment variable.", contexts },
  { reference: "params.mode", group: "Parameters", description: "Build mode.", contexts: ["job", "step", "secret"], job: "build" },
  { reference: "params.other", group: "Parameters", description: "Another job's parameter.", contexts: ["job", "step", "secret"], job: "other" },
  { reference: "secret:service.token", group: "Credentials", description: "Secret reference.", contexts: ["secret"] },
  { reference: "github.ref_name", group: "GitHub", description: "Event ref name.", contexts: ["destination"] },
];
module.exports = { version: 1, entries };
