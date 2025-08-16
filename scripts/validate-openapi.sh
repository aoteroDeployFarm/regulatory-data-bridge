#!/bin/bash
echo "🔍 Validating all OpenAPI specs..."
for file in $(find openapi -name "*.yaml"); do
  echo "Validating: $file"
  npx @redocly/cli lint "$file"
done
