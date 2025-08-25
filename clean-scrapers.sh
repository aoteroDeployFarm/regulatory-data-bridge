# map scrapers.<name> -> scrapers.federal.<name>
declare -a NAMES=(ferc_gov boem_gov bsee_gov epa_gov phmsa_dot_gov)

for name in "${NAMES[@]}"; do
  # from-import
  sed -i '' -E "s#\bfrom\s+scrapers\.${name}\b#from scrapers.federal.${name}#g" $(git ls-files '*.py')
  # plain import
  sed -i '' -E "s#\bimport\s+scrapers\.${name}\b#import scrapers.federal.${name}#g" $(git ls-files '*.py')
done
