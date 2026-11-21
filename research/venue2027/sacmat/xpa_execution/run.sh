#!/usr/bin/env bash
# Run in a NEW scratch directory from a user-provided JDK8, XPA and Z3 install.
set -euo pipefail
study="$(cd "$(dirname "$0")" && pwd)"
: "${XPA:?pinned checkout}" "${JAVA_HOME:?JDK 8}" "${MVN:?Maven binary}" "${Z3:?Z3 executable}"
[[ "$(git -C "$XPA" rev-parse HEAD)" == 89c000495d81a1a82ca8de2ab0fc73fecfc4e440 ]]
git -C "$XPA" diff --exit-code HEAD -- src
work="$(pwd)"
mkdir classes temporary z3
mkdir -p z3/build
"$MVN" -q -B -f "$XPA/pom.xml" -Dmaven.repo.local="${M2:-$work/m2}" \
  dependency:build-classpath -Dmdep.outputFile="$work/runtime.cp"
# Upstream removed Experiment.java but kept a GUI spreadsheet reference to a
# public field. Provide the declaration to javac only; exclude it at runtime.
cat >temporary/Experiment.java <<'JAVA'
package org.seal.xacml.xpa;
public class Experiment { public static String currentPolicyCA; }
JAVA
"$JAVA_HOME/bin/javac" -d temporary temporary/Experiment.java
dependencies="$(cat runtime.cp)"
mkdir probe
"$JAVA_HOME/bin/javac" -XDignore.symbol.file -d probe "$study/Tally.java"
printf 'Premain-Class: Tally\n' > probe.mf
"$JAVA_HOME/bin/jar" cfm probe.jar probe.mf -C probe .
"$JAVA_HOME/bin/javac" -encoding UTF-8 -cp "$dependencies:$work/temporary:$work/probe.jar" \
  -sourcepath "$XPA/src/main/java" -d classes "$study/Execute.java"
[[ ! -e classes/org/seal/xacml/xpa/Experiment.class ]]
cat >z3/build/z3 <<'SH'
#!/bin/sh
printf '%s\n' "$*" >> solver-calls.log
exec "$Z3" "$@"
SH
chmod +x z3/build/z3
probe_options=()
if [[ "${TALLY:-1}" == 1 ]]; then
  probe_options=(-javaagent:probe.jar)
fi
"$JAVA_HOME/bin/java" -Djava.awt.headless=true "${probe_options[@]}" \
  -cp "classes:probe.jar:$XPA/src/main/resources:$dependencies" Execute \
  "$XPA/src/test/resources/org/seal/policies/conference3" generated >generator.log 2>&1
