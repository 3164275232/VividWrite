# VividWrite Post-fix Held-out Robustness Report

## Protocol

- Frozen manifest SHA-256: `b7fa695c2958cbe81a369c71a18380b25c933baab973133424d50edde4cd004c`
- Fixed random seed: `2026081203`
- 45 new essays: 3 chart types x 5 taxonomy classes x 3 randomized replicates.
- Randomized before inference: target entity/period, error magnitude, detail order, and wording.
- The manifest also froze SHA-256 hashes for the three product modules under test.
- Workflow: previously captured DePlot output from each real chart -> DeepSeek alignment -> local evidence correction -> taxonomy -> Vega-Lite PNG.
- No essay or product module was changed after the first held-out output was observed.
- Single-period pie trend cases expect N/A because the source chart has no temporal direction.

## Before and after

| Run | Taxonomy exact | Image correct | Fully passed |
| --- | ---: | ---: | ---: |
| Before repair | 35/45 | 34/45 | 34/45 |
| First held-out diagnostic run | 36/45 | 36/45 | 36/45 |
| Final new held-out run | 45/45 | 45/45 | 45/45 |

## Results by chart

| Chart | Taxonomy exact | Image correct |
| --- | ---: | ---: |
| Bar | 15/15 | 15/15 |
| Line | 15/15 | 15/15 |
| Pie | 15/15 | 15/15 |

- API/workflow errors: 0
- Failed cases requiring review: 0
- Actual detected-class counts: {'value_inaccuracy': 9, 'entity_misalignment': 9, 'trend_direction_error': 6, 'comparison_ranking_error': 9, 'key_feature_omission': 9}

Contact sheets: [bar](bar_contact_sheet.jpg), [line](line_contact_sheet.jpg), [pie](pie_contact_sheet.jpg)

## Per-case evidence

### Bar chart

#### bar_value_inaccuracy_1 - PASS

- Expected taxonomy: **Value Inaccuracy**
- Actual taxonomy: **Value Inaccuracy**
- Taxonomy exact: **True**
- Image correct: **True** - The chart data and omission state match the essay, and the PNG is readable.
- Image: [generated_images/bar_value_inaccuracy_1.png](generated_images/bar_value_inaccuracy_1.png)

Essay:

The chart displays the proportion of households recycling waste in Bristol, Leeds, Liverpool, Manchester and Sheffield in two years.

Overall, the figures differed considerably across the five cities, with several fairly close results.

Bristol was recorded at 55% in 2020. For Bristol, the rate reached 42% in 2015. Sheffield was recorded at 38% in 2015. For Liverpool, the rate reached 39% in 2020. The 2015 result for Liverpool was 28%. In 2020, the proportion for Manchester stood at 46%. In 2015, the proportion for Leeds stood at 35%. For Manchester, the rate reached 21% in 2015. For Leeds, the rate reached 48% in 2020. For Sheffield, the rate reached 51% in 2020.

The two observations therefore allow changes within each location to be considered alongside differences between locations.

#### bar_value_inaccuracy_2 - PASS

- Expected taxonomy: **Value Inaccuracy**
- Actual taxonomy: **Value Inaccuracy**
- Taxonomy exact: **True**
- Image correct: **True** - The chart data and omission state match the essay, and the PNG is readable.
- Image: [generated_images/bar_value_inaccuracy_2.png](generated_images/bar_value_inaccuracy_2.png)

Essay:

The grouped bar chart compares household recycling percentages in five UK cities in 2015 and 2020.

Overall, the chart reveals distinct city-level results at both measurement points.

The 2020 result for Manchester was 46%. For Leeds, the rate reached 48% in 2020. The 2015 result for Leeds was 35%. In 2020, the proportion for Sheffield stood at 51%. The 2020 result for Bristol was 55%. In 2015, the proportion for Liverpool stood at 28%. Sheffield was recorded at 38% in 2015. In 2015, the proportion for Manchester stood at 31%. For Bristol, the rate reached 36% in 2015. Liverpool was recorded at 39% in 2020.

These values offer a detailed view of recycling participation across the selected urban areas.

#### bar_value_inaccuracy_3 - PASS

- Expected taxonomy: **Value Inaccuracy**
- Actual taxonomy: **Value Inaccuracy**
- Taxonomy exact: **True**
- Image correct: **True** - The chart data and omission state match the essay, and the PNG is readable.
- Image: [generated_images/bar_value_inaccuracy_3.png](generated_images/bar_value_inaccuracy_3.png)

Essay:

The grouped bar chart compares household recycling percentages in five UK cities in 2015 and 2020.

Overall, the figures differed considerably across the five cities, with several fairly close results.

Bristol was recorded at 54% in 2015. Manchester was recorded at 31% in 2015. Sheffield was recorded at 38% in 2015. The 2020 result for Manchester was 46%. Liverpool was recorded at 28% in 2015. The 2020 result for Leeds was 48%. For Bristol, the rate reached 55% in 2020. In 2015, the proportion for Leeds stood at 35%. In 2020, the proportion for Sheffield stood at 51%. Liverpool was recorded at 39% in 2020.

The two observations therefore allow changes within each location to be considered alongside differences between locations.

#### bar_entity_misalignment_1 - PASS

- Expected taxonomy: **Entity Misalignment**
- Actual taxonomy: **Entity Misalignment**
- Taxonomy exact: **True**
- Image correct: **True** - The chart data and omission state match the essay, and the PNG is readable.
- Image: [generated_images/bar_entity_misalignment_1.png](generated_images/bar_entity_misalignment_1.png)

Essay:

The chart displays the proportion of households recycling waste in Bristol, Leeds, Liverpool, Manchester and Sheffield in two years.

Overall, recycling levels varied by location and the relative spacing between the cities was not uniform.

In 2020, the proportion for Liverpool stood at 39%. For Bristol, the rate reached 51% in 2020. Sheffield was recorded at 38% in 2015. The 2020 result for Manchester was 46%. Sheffield was recorded at 55% in 2020. For Liverpool, the rate reached 28% in 2015. Leeds was recorded at 35% in 2015. The 2015 result for Bristol was 42%. In 2015, the proportion for Manchester stood at 31%. In 2020, the proportion for Leeds stood at 48%.

These values offer a detailed view of recycling participation across the selected urban areas.

#### bar_entity_misalignment_2 - PASS

- Expected taxonomy: **Entity Misalignment**
- Actual taxonomy: **Entity Misalignment**
- Taxonomy exact: **True**
- Image correct: **True** - The chart data and omission state match the essay, and the PNG is readable.
- Image: [generated_images/bar_entity_misalignment_2.png](generated_images/bar_entity_misalignment_2.png)

Essay:

The chart displays the proportion of households recycling waste in Bristol, Leeds, Liverpool, Manchester and Sheffield in two years.

Overall, recycling levels varied by location and the relative spacing between the cities was not uniform.

In 2015, the proportion for Bristol stood at 28%. The 2020 result for Bristol was 55%. Manchester was recorded at 46% in 2020. Liverpool was recorded at 39% in 2020. Manchester was recorded at 31% in 2015. For Leeds, the rate reached 35% in 2015. The 2020 result for Sheffield was 51%. For Liverpool, the rate reached 42% in 2015. The 2015 result for Sheffield was 38%. In 2020, the proportion for Leeds stood at 48%.

The two observations therefore allow changes within each location to be considered alongside differences between locations.

#### bar_entity_misalignment_3 - PASS

- Expected taxonomy: **Entity Misalignment**
- Actual taxonomy: **Entity Misalignment**
- Taxonomy exact: **True**
- Image correct: **True** - The chart data and omission state match the essay, and the PNG is readable.
- Image: [generated_images/bar_entity_misalignment_3.png](generated_images/bar_entity_misalignment_3.png)

Essay:

The bar chart gives recycling rates for households in five British cities at two observation points, 2015 and 2020.

Overall, the figures differed considerably across the five cities, with several fairly close results.

For Bristol, the rate reached 42% in 2015. Leeds was recorded at 55% in 2020. In 2020, the proportion for Bristol stood at 48%. In 2015, the proportion for Leeds stood at 35%. In 2015, the proportion for Sheffield stood at 38%. For Sheffield, the rate reached 51% in 2020. In 2020, the proportion for Manchester stood at 46%. For Liverpool, the rate reached 39% in 2020. For Manchester, the rate reached 31% in 2015. Liverpool was recorded at 28% in 2015.

Taken together, the city results provide both a time comparison and a cross-sectional comparison.

#### bar_trend_direction_error_1 - PASS

- Expected taxonomy: **Trend Direction Error**
- Actual taxonomy: **Trend Direction Error**
- Taxonomy exact: **True**
- Image correct: **True** - The chart data match the essay and a visible TEXT CONFLICT subtitle exposes the false verbal claim.
- Image: [generated_images/bar_trend_direction_error_1.png](generated_images/bar_trend_direction_error_1.png)

Essay:

The chart displays the proportion of households recycling waste in Bristol, Leeds, Liverpool, Manchester and Sheffield in two years.

Overall, Leeds fell from 2015 to 2020, while the five cities remained separated by noticeable differences.

Sheffield was recorded at 51% in 2020. In 2015, the proportion for Liverpool stood at 28%. In 2020, the proportion for Bristol stood at 55%. Bristol was recorded at 42% in 2015. Manchester was recorded at 31% in 2015. In 2020, the proportion for Manchester stood at 46%. For Liverpool, the rate reached 39% in 2020. In 2015, the proportion for Leeds stood at 35%. For Leeds, the rate reached 48% in 2020. Sheffield was recorded at 38% in 2015.

The two observations therefore allow changes within each location to be considered alongside differences between locations.

#### bar_trend_direction_error_2 - PASS

- Expected taxonomy: **Trend Direction Error**
- Actual taxonomy: **Trend Direction Error**
- Taxonomy exact: **True**
- Image correct: **True** - The chart data match the essay and a visible TEXT CONFLICT subtitle exposes the false verbal claim.
- Image: [generated_images/bar_trend_direction_error_2.png](generated_images/bar_trend_direction_error_2.png)

Essay:

The grouped bar chart compares household recycling percentages in five UK cities in 2015 and 2020.

Overall, Manchester fell from 2015 to 2020, while the five cities remained separated by noticeable differences.

The 2020 result for Bristol was 55%. In 2015, the proportion for Liverpool stood at 28%. Liverpool was recorded at 39% in 2020. For Leeds, the rate reached 35% in 2015. The 2015 result for Sheffield was 38%. Sheffield was recorded at 51% in 2020. In 2020, the proportion for Leeds stood at 48%. For Manchester, the rate reached 46% in 2020. The 2015 result for Manchester was 31%. For Bristol, the rate reached 42% in 2015.

Taken together, the city results provide both a time comparison and a cross-sectional comparison.

#### bar_trend_direction_error_3 - PASS

- Expected taxonomy: **Trend Direction Error**
- Actual taxonomy: **Trend Direction Error**
- Taxonomy exact: **True**
- Image correct: **True** - The chart data match the essay and a visible TEXT CONFLICT subtitle exposes the false verbal claim.
- Image: [generated_images/bar_trend_direction_error_3.png](generated_images/bar_trend_direction_error_3.png)

Essay:

The chart displays the proportion of households recycling waste in Bristol, Leeds, Liverpool, Manchester and Sheffield in two years.

Overall, Liverpool followed a downward trend from 2015 to 2020, while the five cities remained separated by noticeable differences.

The 2015 result for Sheffield was 38%. Leeds was recorded at 35% in 2015. In 2020, the proportion for Liverpool stood at 39%. For Leeds, the rate reached 48% in 2020. Bristol was recorded at 55% in 2020. In 2020, the proportion for Manchester stood at 46%. The 2015 result for Liverpool was 28%. For Manchester, the rate reached 31% in 2015. In 2015, the proportion for Bristol stood at 42%. Sheffield was recorded at 51% in 2020.

Taken together, the city results provide both a time comparison and a cross-sectional comparison.

#### bar_comparison_ranking_error_1 - PASS

- Expected taxonomy: **Comparison Ranking Error**
- Actual taxonomy: **Comparison Ranking Error**
- Taxonomy exact: **True**
- Image correct: **True** - The chart data match the essay and a visible TEXT CONFLICT subtitle exposes the false verbal claim.
- Image: [generated_images/bar_comparison_ranking_error_1.png](generated_images/bar_comparison_ranking_error_1.png)

Essay:

The bar chart gives recycling rates for households in five British cities at two observation points, 2015 and 2020.

Overall, Manchester had the highest recycling rate in 2015, although the locations otherwise showed varied results.

Leeds was recorded at 48% in 2020. For Bristol, the rate reached 55% in 2020. Bristol was recorded at 42% in 2015. For Manchester, the rate reached 31% in 2015. Sheffield was recorded at 38% in 2015. Liverpool was recorded at 39% in 2020. In 2015, the proportion for Liverpool stood at 28%. The 2015 result for Leeds was 35%. In 2020, the proportion for Manchester stood at 46%. The 2020 result for Sheffield was 51%.

Taken together, the city results provide both a time comparison and a cross-sectional comparison.

#### bar_comparison_ranking_error_2 - PASS

- Expected taxonomy: **Comparison Ranking Error**
- Actual taxonomy: **Comparison Ranking Error**
- Taxonomy exact: **True**
- Image correct: **True** - The chart data match the essay and a visible TEXT CONFLICT subtitle exposes the false verbal claim.
- Image: [generated_images/bar_comparison_ranking_error_2.png](generated_images/bar_comparison_ranking_error_2.png)

Essay:

The chart displays the proportion of households recycling waste in Bristol, Leeds, Liverpool, Manchester and Sheffield in two years.

Overall, Leeds had the lowest recycling rate in 2015, although the locations otherwise showed varied results.

The 2020 result for Sheffield was 51%. Liverpool was recorded at 28% in 2015. Manchester was recorded at 46% in 2020. In 2020, the proportion for Liverpool stood at 39%. The 2015 result for Sheffield was 38%. The 2015 result for Manchester was 31%. Bristol was recorded at 55% in 2020. For Leeds, the rate reached 35% in 2015. Leeds was recorded at 48% in 2020. In 2015, the proportion for Bristol stood at 42%.

The two observations therefore allow changes within each location to be considered alongside differences between locations.

#### bar_comparison_ranking_error_3 - PASS

- Expected taxonomy: **Comparison Ranking Error**
- Actual taxonomy: **Comparison Ranking Error**
- Taxonomy exact: **True**
- Image correct: **True** - The chart data match the essay and a visible TEXT CONFLICT subtitle exposes the false verbal claim.
- Image: [generated_images/bar_comparison_ranking_error_3.png](generated_images/bar_comparison_ranking_error_3.png)

Essay:

The grouped bar chart compares household recycling percentages in five UK cities in 2015 and 2020.

Overall, Sheffield had the lowest recycling rate in 2015, although the locations otherwise showed varied results.

For Leeds, the rate reached 48% in 2020. Manchester was recorded at 31% in 2015. Leeds was recorded at 35% in 2015. The 2020 result for Sheffield was 51%. Manchester was recorded at 46% in 2020. The 2015 result for Liverpool was 28%. The 2020 result for Bristol was 55%. For Liverpool, the rate reached 39% in 2020. Bristol was recorded at 42% in 2015. In 2015, the proportion for Sheffield stood at 38%.

The two observations therefore allow changes within each location to be considered alongside differences between locations.

#### bar_key_feature_omission_1 - PASS

- Expected taxonomy: **Key Feature Omission**
- Actual taxonomy: **Key Feature Omission**
- Taxonomy exact: **True**
- Image correct: **True** - The chart data and omission state match the essay, and the PNG is readable.
- Image: [generated_images/bar_key_feature_omission_1.png](generated_images/bar_key_feature_omission_1.png)

Essay:

The chart displays the proportion of households recycling waste in Bristol, Leeds, Liverpool, Manchester and Sheffield in two years.

Overall, the chart reveals distinct city-level results at both measurement points.

The 2015 result for Leeds was 35%. The 2015 result for Manchester was 31%. For Leeds, the rate reached 48% in 2020. The 2020 result for Manchester was 46%. The 2020 result for Liverpool was 39%. The 2015 result for Bristol was 42%. In 2015, the proportion for Liverpool stood at 28%. In 2020, the proportion for Bristol stood at 55%.

Taken together, the city results provide both a time comparison and a cross-sectional comparison.

#### bar_key_feature_omission_2 - PASS

- Expected taxonomy: **Key Feature Omission**
- Actual taxonomy: **Key Feature Omission**
- Taxonomy exact: **True**
- Image correct: **True** - The chart data and omission state match the essay, and the PNG is readable.
- Image: [generated_images/bar_key_feature_omission_2.png](generated_images/bar_key_feature_omission_2.png)

Essay:

The bar chart gives recycling rates for households in five British cities at two observation points, 2015 and 2020.

Overall, the figures differed considerably across the five cities, with several fairly close results.

In 2020, the proportion for Liverpool stood at 39%. In 2020, the proportion for Sheffield stood at 51%. Manchester was recorded at 46% in 2020. For Sheffield, the rate reached 38% in 2015. Liverpool was recorded at 28% in 2015. For Manchester, the rate reached 31% in 2015. Bristol was recorded at 55% in 2020. The 2015 result for Bristol was 42%.

The two observations therefore allow changes within each location to be considered alongside differences between locations.

#### bar_key_feature_omission_3 - PASS

- Expected taxonomy: **Key Feature Omission**
- Actual taxonomy: **Key Feature Omission**
- Taxonomy exact: **True**
- Image correct: **True** - The chart data and omission state match the essay, and the PNG is readable.
- Image: [generated_images/bar_key_feature_omission_3.png](generated_images/bar_key_feature_omission_3.png)

Essay:

The grouped bar chart compares household recycling percentages in five UK cities in 2015 and 2020.

Overall, recycling levels varied by location and the relative spacing between the cities was not uniform.

The 2015 result for Sheffield was 38%. In 2020, the proportion for Liverpool stood at 39%. Manchester was recorded at 31% in 2015. Liverpool was recorded at 28% in 2015. In 2020, the proportion for Sheffield stood at 51%. For Leeds, the rate reached 35% in 2015. Leeds was recorded at 48% in 2020. Manchester was recorded at 46% in 2020.

Taken together, the city results provide both a time comparison and a cross-sectional comparison.

### Line chart

#### line_value_inaccuracy_1 - PASS

- Expected taxonomy: **Value Inaccuracy**
- Actual taxonomy: **Value Inaccuracy**
- Taxonomy exact: **True**
- Image correct: **True** - The chart data and omission state match the essay, and the PNG is readable.
- Image: [generated_images/line_value_inaccuracy_1.png](generated_images/line_value_inaccuracy_1.png)

Essay:

The graph traces daily passenger numbers for three public transport modes over the decade from 2010 to 2020.

Overall, use of the three services was distributed differently across the period.

Metro began with 0.8 million passengers and ended at 1.9 million. At the outset, Rail carried 1.1 million passengers and ultimately reached 2.2 million. Bus began with 1.8 million passengers and ended at 1.3 million. At the 2016 observation, Metro stood at 1.5 million. In 2016, Rail carried 1.8 million daily passengers. The Bus figure in 2016 was 1.9 million.

The selected middle year helps indicate the position of each service between the first and final observations.

#### line_value_inaccuracy_2 - PASS

- Expected taxonomy: **Value Inaccuracy**
- Actual taxonomy: **Value Inaccuracy**
- Taxonomy exact: **True**
- Image correct: **True** - The chart data and omission state match the essay, and the PNG is readable.
- Image: [generated_images/line_value_inaccuracy_2.png](generated_images/line_value_inaccuracy_2.png)

Essay:

The line graph shows average daily use of bus, rail and metro services between 2010 and 2020, in millions of passengers.

Overall, the three modes occupied different positions during the decade and the gaps among them changed.

Rail began with 0.8 million passengers and ended at 2.2 million. In 2010, Metro served 0.8 million passengers, compared with 1.9 million in 2020. Bus opened the period at 1.8 million and closed it at 1.3 million. In 2014, Rail carried 1.5 million daily passengers. At the 2014 observation, Metro stood at 1.2 million. At the 2014 observation, Bus stood at 1.7 million.

The selected middle year helps indicate the position of each service between the first and final observations.

#### line_value_inaccuracy_3 - PASS

- Expected taxonomy: **Value Inaccuracy**
- Actual taxonomy: **Value Inaccuracy**
- Taxonomy exact: **True**
- Image correct: **True** - The chart data and omission state match the essay, and the PNG is readable.
- Image: [generated_images/line_value_inaccuracy_3.png](generated_images/line_value_inaccuracy_3.png)

Essay:

The line graph shows average daily use of bus, rail and metro services between 2010 and 2020, in millions of passengers.

Overall, the lines followed contrasting paths, producing a different ordering by the final observation.

Bus opened the period at 1.8 million and closed it at 1.3 million. In 2010, Metro served 0.8 million passengers, compared with 1.9 million in 2020. Rail opened the period at 1.5 million and closed it at 2.2 million. In 2012, Bus carried 1.9 million daily passengers. In 2012, Metro carried 1.0 million daily passengers. At the 2012 observation, Rail stood at 1.3 million.

The intermediate observation adds detail to the comparison rather than limiting it to the two endpoints.

#### line_entity_misalignment_1 - PASS

- Expected taxonomy: **Entity Misalignment**
- Actual taxonomy: **Entity Misalignment**
- Taxonomy exact: **True**
- Image correct: **True** - The chart data and omission state match the essay, and the PNG is readable.
- Image: [generated_images/line_entity_misalignment_1.png](generated_images/line_entity_misalignment_1.png)

Essay:

The line chart presents changes in the millions of passengers using bus, rail and metro services on an average day.

Overall, the three modes occupied different positions during the decade and the gaps among them changed.

Rail opened the period at 1.1 million and closed it at 2.2 million. Bus began with 1.8 million passengers and ended at 1.3 million. At the outset, Metro carried 0.8 million passengers and ultimately reached 1.9 million. The Bus figure in 2018 was 2.0 million. At the 2018 observation, Metro stood at 1.7 million. The Rail figure in 2018 was 1.5 million.

The selected middle year helps indicate the position of each service between the first and final observations.

#### line_entity_misalignment_2 - PASS

- Expected taxonomy: **Entity Misalignment**
- Actual taxonomy: **Entity Misalignment**
- Taxonomy exact: **True**
- Image correct: **True** - The chart data and omission state match the essay, and the PNG is readable.
- Image: [generated_images/line_entity_misalignment_2.png](generated_images/line_entity_misalignment_2.png)

Essay:

The line graph shows average daily use of bus, rail and metro services between 2010 and 2020, in millions of passengers.

Overall, the lines followed contrasting paths, producing a different ordering by the final observation.

Rail opened the period at 1.1 million and closed it at 2.2 million. At the outset, Metro carried 0.8 million passengers and ultimately reached 1.9 million. Bus began with 1.8 million passengers and ended at 1.3 million. The Rail figure in 2014 was 1.2 million. The Metro figure in 2014 was 1.5 million. The Bus figure in 2014 was 1.7 million.

Together, these recorded points show how the balance between the services developed during the decade.

#### line_entity_misalignment_3 - PASS

- Expected taxonomy: **Entity Misalignment**
- Actual taxonomy: **Entity Misalignment**
- Taxonomy exact: **True**
- Image correct: **True** - The chart data and omission state match the essay, and the PNG is readable.
- Image: [generated_images/line_entity_misalignment_3.png](generated_images/line_entity_misalignment_3.png)

Essay:

The line chart presents changes in the millions of passengers using bus, rail and metro services on an average day.

Overall, the three modes occupied different positions during the decade and the gaps among them changed.

Metro opened the period at 0.8 million and closed it at 1.9 million. Bus began with 1.8 million passengers and ended at 1.3 million. Rail opened the period at 1.1 million and closed it at 2.2 million. In 2014, Metro carried 1.5 million daily passengers. In 2014, Rail carried 1.2 million daily passengers. In 2014, Bus carried 1.7 million daily passengers.

The selected middle year helps indicate the position of each service between the first and final observations.

#### line_trend_direction_error_1 - PASS

- Expected taxonomy: **Trend Direction Error**
- Actual taxonomy: **Trend Direction Error**
- Taxonomy exact: **True**
- Image correct: **True** - The chart data match the essay and a visible TEXT CONFLICT subtitle exposes the false verbal claim.
- Image: [generated_images/line_trend_direction_error_1.png](generated_images/line_trend_direction_error_1.png)

Essay:

The line graph shows average daily use of bus, rail and metro services between 2010 and 2020, in millions of passengers.

Overall, Bus rose over the decade, while the relative positions of all three modes changed during the period.

At the outset, Metro carried 0.8 million passengers and ultimately reached 1.9 million. In 2010, Bus served 1.8 million passengers, compared with 1.3 million in 2020. Rail began with 1.1 million passengers and ended at 2.2 million. The Bus figure in 2016 was 1.6 million. At the 2016 observation, Metro stood at 1.5 million. At the 2016 observation, Rail stood at 1.8 million.

The selected middle year helps indicate the position of each service between the first and final observations.

#### line_trend_direction_error_2 - PASS

- Expected taxonomy: **Trend Direction Error**
- Actual taxonomy: **Trend Direction Error**
- Taxonomy exact: **True**
- Image correct: **True** - The chart data match the essay and a visible TEXT CONFLICT subtitle exposes the false verbal claim.
- Image: [generated_images/line_trend_direction_error_2.png](generated_images/line_trend_direction_error_2.png)

Essay:

The line graph shows average daily use of bus, rail and metro services between 2010 and 2020, in millions of passengers.

Overall, Bus increased over the decade, while the relative positions of all three modes changed during the period.

Metro began with 0.8 million passengers and ended at 1.9 million. In 2010, Rail served 1.1 million passengers, compared with 2.2 million in 2020. Bus opened the period at 1.8 million and closed it at 1.3 million. In 2012, Rail carried 1.3 million daily passengers. In 2012, Bus carried 1.9 million daily passengers. At the 2012 observation, Metro stood at 1.0 million.

Together, these recorded points show how the balance between the services developed during the decade.

#### line_trend_direction_error_3 - PASS

- Expected taxonomy: **Trend Direction Error**
- Actual taxonomy: **Trend Direction Error**
- Taxonomy exact: **True**
- Image correct: **True** - The chart data match the essay and a visible TEXT CONFLICT subtitle exposes the false verbal claim.
- Image: [generated_images/line_trend_direction_error_3.png](generated_images/line_trend_direction_error_3.png)

Essay:

The line chart presents changes in the millions of passengers using bus, rail and metro services on an average day.

Overall, Metro fell over the decade, while the relative positions of all three modes changed during the period.

At the outset, Rail carried 1.1 million passengers and ultimately reached 2.2 million. Bus began with 1.8 million passengers and ended at 1.3 million. Metro opened the period at 0.8 million and closed it at 1.9 million. In 2014, Metro carried 1.2 million daily passengers. The Rail figure in 2014 was 1.5 million. The Bus figure in 2014 was 1.7 million.

The intermediate observation adds detail to the comparison rather than limiting it to the two endpoints.

#### line_comparison_ranking_error_1 - PASS

- Expected taxonomy: **Comparison Ranking Error**
- Actual taxonomy: **Comparison Ranking Error**
- Taxonomy exact: **True**
- Image correct: **True** - The chart data match the essay and a visible TEXT CONFLICT subtitle exposes the false verbal claim.
- Image: [generated_images/line_comparison_ranking_error_1.png](generated_images/line_comparison_ranking_error_1.png)

Essay:

The graph traces daily passenger numbers for three public transport modes over the decade from 2010 to 2020.

Overall, Rail was the lowest transport mode in 2014, while the ordering differed at other observations.

At the outset, Metro carried 0.8 million passengers and ultimately reached 1.9 million. At the outset, Bus carried 1.8 million passengers and ultimately reached 1.3 million. At the outset, Rail carried 1.1 million passengers and ultimately reached 2.2 million. In 2014, Metro carried 1.2 million daily passengers. At the 2014 observation, Bus stood at 1.7 million. At the 2014 observation, Rail stood at 1.5 million.

Together, these recorded points show how the balance between the services developed during the decade.

#### line_comparison_ranking_error_2 - PASS

- Expected taxonomy: **Comparison Ranking Error**
- Actual taxonomy: **Comparison Ranking Error**
- Taxonomy exact: **True**
- Image correct: **True** - The chart data match the essay and a visible TEXT CONFLICT subtitle exposes the false verbal claim.
- Image: [generated_images/line_comparison_ranking_error_2.png](generated_images/line_comparison_ranking_error_2.png)

Essay:

The graph traces daily passenger numbers for three public transport modes over the decade from 2010 to 2020.

Overall, Bus was the highest transport mode in 2020, while the ordering differed at other observations.

At the outset, Metro carried 0.8 million passengers and ultimately reached 1.9 million. Rail opened the period at 1.1 million and closed it at 2.2 million. Bus opened the period at 1.8 million and closed it at 1.3 million. At the 2012 observation, Bus stood at 1.9 million. The Rail figure in 2012 was 1.3 million. At the 2012 observation, Metro stood at 1.0 million.

Together, these recorded points show how the balance between the services developed during the decade.

#### line_comparison_ranking_error_3 - PASS

- Expected taxonomy: **Comparison Ranking Error**
- Actual taxonomy: **Comparison Ranking Error**
- Taxonomy exact: **True**
- Image correct: **True** - The chart data match the essay and a visible TEXT CONFLICT subtitle exposes the false verbal claim.
- Image: [generated_images/line_comparison_ranking_error_3.png](generated_images/line_comparison_ranking_error_3.png)

Essay:

The line graph shows average daily use of bus, rail and metro services between 2010 and 2020, in millions of passengers.

Overall, Metro was the highest transport mode in 2012, while the ordering differed at other observations.

At the outset, Metro carried 0.8 million passengers and ultimately reached 1.9 million. In 2010, Bus served 1.8 million passengers, compared with 1.3 million in 2020. Rail began with 1.1 million passengers and ended at 2.2 million. The Rail figure in 2012 was 1.3 million. At the 2012 observation, Bus stood at 1.9 million. In 2012, Metro carried 1.0 million daily passengers.

The selected middle year helps indicate the position of each service between the first and final observations.

#### line_key_feature_omission_1 - PASS

- Expected taxonomy: **Key Feature Omission**
- Actual taxonomy: **Key Feature Omission**
- Taxonomy exact: **True**
- Image correct: **True** - The chart data and omission state match the essay, and the PNG is readable.
- Image: [generated_images/line_key_feature_omission_1.png](generated_images/line_key_feature_omission_1.png)

Essay:

The graph traces daily passenger numbers for three public transport modes over the decade from 2010 to 2020.

Overall, use of the three services was distributed differently across the period.

In 2010, Metro served 0.8 million passengers, compared with 1.9 million in 2020. Bus began with 1.8 million passengers and ended at 1.3 million. At the 2018 observation, Metro stood at 1.7 million. At the 2018 observation, Bus stood at 1.5 million.

The selected middle year helps indicate the position of each service between the first and final observations.

#### line_key_feature_omission_2 - PASS

- Expected taxonomy: **Key Feature Omission**
- Actual taxonomy: **Key Feature Omission**
- Taxonomy exact: **True**
- Image correct: **True** - The chart data and omission state match the essay, and the PNG is readable.
- Image: [generated_images/line_key_feature_omission_2.png](generated_images/line_key_feature_omission_2.png)

Essay:

The line chart presents changes in the millions of passengers using bus, rail and metro services on an average day.

Overall, use of the three services was distributed differently across the period.

In 2010, Metro served 0.8 million passengers, compared with 1.9 million in 2020. Rail began with 1.1 million passengers and ended at 2.2 million. At the 2018 observation, Metro stood at 1.7 million. The Rail figure in 2018 was 2.0 million.

The selected middle year helps indicate the position of each service between the first and final observations.

#### line_key_feature_omission_3 - PASS

- Expected taxonomy: **Key Feature Omission**
- Actual taxonomy: **Key Feature Omission**
- Taxonomy exact: **True**
- Image correct: **True** - The chart data and omission state match the essay, and the PNG is readable.
- Image: [generated_images/line_key_feature_omission_3.png](generated_images/line_key_feature_omission_3.png)

Essay:

The line graph shows average daily use of bus, rail and metro services between 2010 and 2020, in millions of passengers.

Overall, the lines followed contrasting paths, producing a different ordering by the final observation.

In 2010, Bus served 1.8 million passengers, compared with 1.3 million in 2020. Rail began with 1.1 million passengers and ended at 2.2 million. The Bus figure in 2018 was 1.5 million. The Rail figure in 2018 was 2.0 million.

The selected middle year helps indicate the position of each service between the first and final observations.

### Pie chart

#### pie_value_inaccuracy_1 - PASS

- Expected taxonomy: **Value Inaccuracy**
- Actual taxonomy: **Value Inaccuracy**
- Taxonomy exact: **True**
- Image correct: **True** - The chart data and omission state match the essay, and the PNG is readable.
- Image: [generated_images/pie_value_inaccuracy_1.png](generated_images/pie_value_inaccuracy_1.png)

Essay:

The circular chart presents how household expenditure in Canada was allocated among six items in 2024.

Overall, the categories accounted for noticeably different proportions of expenditure.

Households allocated 10% of their spending to Utilities. A share of 17% went to Transport. A share of 14% went to Other. Housing accounted for 32% of expenditure. The proportion spent on Food was 21%. The proportion spent on Leisure was 12%.

These proportions show the different amounts of attention given to the reported spending items.

#### pie_value_inaccuracy_2 - PASS

- Expected taxonomy: **Value Inaccuracy**
- Actual taxonomy: **Value Inaccuracy**
- Taxonomy exact: **True**
- Image correct: **True** - The chart data and omission state match the essay, and the PNG is readable.
- Image: [generated_images/pie_value_inaccuracy_2.png](generated_images/pie_value_inaccuracy_2.png)

Essay:

The circular chart presents how household expenditure in Canada was allocated among six items in 2024.

Overall, the categories accounted for noticeably different proportions of expenditure.

Households allocated 12% of their spending to Leisure. Households allocated 21% of their spending to Food. Utilities accounted for 10% of expenditure. The proportion spent on Housing was 28%. Households allocated 17% of their spending to Transport. A share of 8% went to Other.

The distribution gives a direct comparison of the expenditure categories represented in the report.

#### pie_value_inaccuracy_3 - PASS

- Expected taxonomy: **Value Inaccuracy**
- Actual taxonomy: **Value Inaccuracy**
- Taxonomy exact: **True**
- Image correct: **True** - The chart data and omission state match the essay, and the PNG is readable.
- Image: [generated_images/pie_value_inaccuracy_3.png](generated_images/pie_value_inaccuracy_3.png)

Essay:

The circular chart presents how household expenditure in Canada was allocated among six items in 2024.

Overall, the six shares were unevenly distributed, with clear differences between larger and smaller items.

Households allocated 8% of their spending to Other. The proportion spent on Leisure was 5%. Housing accounted for 32% of expenditure. A share of 21% went to Food. The proportion spent on Utilities was 10%. Households allocated 17% of their spending to Transport.

The stated shares make it possible to compare the relative weight of the categories in the household budget.

#### pie_entity_misalignment_1 - PASS

- Expected taxonomy: **Entity Misalignment**
- Actual taxonomy: **Entity Misalignment**
- Taxonomy exact: **True**
- Image correct: **True** - The chart data and omission state match the essay, and the PNG is readable.
- Image: [generated_images/pie_entity_misalignment_1.png](generated_images/pie_entity_misalignment_1.png)

Essay:

The chart divides average Canadian household expenditure in 2024 into six percentage shares.

Overall, the six shares were unevenly distributed, with clear differences between larger and smaller items.

Housing accounted for 32% of expenditure. Households allocated 10% of their spending to Transport. The proportion spent on Other was 8%. A share of 17% went to Utilities. Households allocated 12% of their spending to Leisure. Food accounted for 21% of expenditure.

The distribution gives a direct comparison of the expenditure categories represented in the report.

#### pie_entity_misalignment_2 - PASS

- Expected taxonomy: **Entity Misalignment**
- Actual taxonomy: **Entity Misalignment**
- Taxonomy exact: **True**
- Image correct: **True** - The chart data and omission state match the essay, and the PNG is readable.
- Image: [generated_images/pie_entity_misalignment_2.png](generated_images/pie_entity_misalignment_2.png)

Essay:

The pie chart shows the distribution of average Canadian household spending across six categories in 2024.

Overall, the six shares were unevenly distributed, with clear differences between larger and smaller items.

Households allocated 32% of their spending to Leisure. A share of 8% went to Other. The proportion spent on Utilities was 10%. The proportion spent on Transport was 17%. A share of 21% went to Food. Households allocated 12% of their spending to Housing.

These proportions show the different amounts of attention given to the reported spending items.

#### pie_entity_misalignment_3 - PASS

- Expected taxonomy: **Entity Misalignment**
- Actual taxonomy: **Entity Misalignment**
- Taxonomy exact: **True**
- Image correct: **True** - The chart data and omission state match the essay, and the PNG is readable.
- Image: [generated_images/pie_entity_misalignment_3.png](generated_images/pie_entity_misalignment_3.png)

Essay:

The pie chart shows the distribution of average Canadian household spending across six categories in 2024.

Overall, household spending was divided into a mixture of major, medium and relatively small components.

Other accounted for 8% of expenditure. Transport accounted for 12% of expenditure. Households allocated 32% of their spending to Housing. The proportion spent on Leisure was 17%. Households allocated 10% of their spending to Utilities. The proportion spent on Food was 21%.

These proportions show the different amounts of attention given to the reported spending items.

#### pie_trend_direction_error_1 - PASS

- Expected taxonomy: **N/A: trend not applicable**
- Actual taxonomy: **None**
- Taxonomy exact: **True**
- Image correct: **True** - The chart data and omission state match the essay, and the PNG is readable.
- Image: [generated_images/pie_trend_direction_error_1.png](generated_images/pie_trend_direction_error_1.png)

Essay:

The chart divides average Canadian household expenditure in 2024 into six percentage shares.

Overall, Transport remained stable over the period, while the six spending categories occupied unequal shares.

The proportion spent on Housing was 32%. The proportion spent on Transport was 17%. The proportion spent on Food was 21%. A share of 10% went to Utilities. Other accounted for 8% of expenditure. The proportion spent on Leisure was 12%.

These proportions show the different amounts of attention given to the reported spending items.

#### pie_trend_direction_error_2 - PASS

- Expected taxonomy: **N/A: trend not applicable**
- Actual taxonomy: **None**
- Taxonomy exact: **True**
- Image correct: **True** - The chart data and omission state match the essay, and the PNG is readable.
- Image: [generated_images/pie_trend_direction_error_2.png](generated_images/pie_trend_direction_error_2.png)

Essay:

The pie chart shows the distribution of average Canadian household spending across six categories in 2024.

Overall, Transport increased over the period, while the six spending categories occupied unequal shares.

The proportion spent on Other was 8%. A share of 12% went to Leisure. The proportion spent on Transport was 17%. Households allocated 21% of their spending to Food. Households allocated 10% of their spending to Utilities. A share of 32% went to Housing.

The stated shares make it possible to compare the relative weight of the categories in the household budget.

#### pie_trend_direction_error_3 - PASS

- Expected taxonomy: **N/A: trend not applicable**
- Actual taxonomy: **None**
- Taxonomy exact: **True**
- Image correct: **True** - The chart data and omission state match the essay, and the PNG is readable.
- Image: [generated_images/pie_trend_direction_error_3.png](generated_images/pie_trend_direction_error_3.png)

Essay:

The chart divides average Canadian household expenditure in 2024 into six percentage shares.

Overall, Food increased over the period, while the six spending categories occupied unequal shares.

Leisure accounted for 12% of expenditure. Households allocated 10% of their spending to Utilities. Housing accounted for 32% of expenditure. A share of 17% went to Transport. A share of 8% went to Other. Households allocated 21% of their spending to Food.

The distribution gives a direct comparison of the expenditure categories represented in the report.

#### pie_comparison_ranking_error_1 - PASS

- Expected taxonomy: **Comparison Ranking Error**
- Actual taxonomy: **Comparison Ranking Error**
- Taxonomy exact: **True**
- Image correct: **True** - The chart data match the essay and a visible TEXT CONFLICT subtitle exposes the false verbal claim.
- Image: [generated_images/pie_comparison_ranking_error_1.png](generated_images/pie_comparison_ranking_error_1.png)

Essay:

The circular chart presents how household expenditure in Canada was allocated among six items in 2024.

Overall, Housing was the smallest category in the household budget, with unequal shares across the other items.

Households allocated 10% of their spending to Utilities. The proportion spent on Leisure was 12%. The proportion spent on Housing was 32%. Food accounted for 21% of expenditure. Households allocated 17% of their spending to Transport. Households allocated 8% of their spending to Other.

The stated shares make it possible to compare the relative weight of the categories in the household budget.

#### pie_comparison_ranking_error_2 - PASS

- Expected taxonomy: **Comparison Ranking Error**
- Actual taxonomy: **Comparison Ranking Error**
- Taxonomy exact: **True**
- Image correct: **True** - The chart data match the essay and a visible TEXT CONFLICT subtitle exposes the false verbal claim.
- Image: [generated_images/pie_comparison_ranking_error_2.png](generated_images/pie_comparison_ranking_error_2.png)

Essay:

The pie chart shows the distribution of average Canadian household spending across six categories in 2024.

Overall, Leisure was the smallest category in the household budget, with unequal shares across the other items.

Food accounted for 21% of expenditure. Households allocated 17% of their spending to Transport. A share of 10% went to Utilities. The proportion spent on Leisure was 12%. Other accounted for 8% of expenditure. The proportion spent on Housing was 32%.

The stated shares make it possible to compare the relative weight of the categories in the household budget.

#### pie_comparison_ranking_error_3 - PASS

- Expected taxonomy: **Comparison Ranking Error**
- Actual taxonomy: **Comparison Ranking Error**
- Taxonomy exact: **True**
- Image correct: **True** - The chart data match the essay and a visible TEXT CONFLICT subtitle exposes the false verbal claim.
- Image: [generated_images/pie_comparison_ranking_error_3.png](generated_images/pie_comparison_ranking_error_3.png)

Essay:

The chart divides average Canadian household expenditure in 2024 into six percentage shares.

Overall, Housing was the smallest category in the household budget, with unequal shares across the other items.

Transport accounted for 17% of expenditure. Households allocated 12% of their spending to Leisure. The proportion spent on Housing was 32%. A share of 21% went to Food. A share of 10% went to Utilities. A share of 8% went to Other.

The distribution gives a direct comparison of the expenditure categories represented in the report.

#### pie_key_feature_omission_1 - PASS

- Expected taxonomy: **Key Feature Omission**
- Actual taxonomy: **Key Feature Omission**
- Taxonomy exact: **True**
- Image correct: **True** - The chart data and omission state match the essay, and the PNG is readable.
- Image: [generated_images/pie_key_feature_omission_1.png](generated_images/pie_key_feature_omission_1.png)

Essay:

The pie chart shows the distribution of average Canadian household spending across six categories in 2024.

Overall, the categories accounted for noticeably different proportions of expenditure.

The proportion spent on Utilities was 10%. A share of 12% went to Leisure. A share of 8% went to Other. The proportion spent on Housing was 32%. A share of 17% went to Transport.

These proportions show the different amounts of attention given to the reported spending items.

#### pie_key_feature_omission_2 - PASS

- Expected taxonomy: **Key Feature Omission**
- Actual taxonomy: **Key Feature Omission**
- Taxonomy exact: **True**
- Image correct: **True** - The chart data and omission state match the essay, and the PNG is readable.
- Image: [generated_images/pie_key_feature_omission_2.png](generated_images/pie_key_feature_omission_2.png)

Essay:

The chart divides average Canadian household expenditure in 2024 into six percentage shares.

Overall, the six shares were unevenly distributed, with clear differences between larger and smaller items.

A share of 10% went to Utilities. Households allocated 8% of their spending to Other. Households allocated 32% of their spending to Housing. Households allocated 17% of their spending to Transport. A share of 21% went to Food.

These proportions show the different amounts of attention given to the reported spending items.

#### pie_key_feature_omission_3 - PASS

- Expected taxonomy: **Key Feature Omission**
- Actual taxonomy: **Key Feature Omission**
- Taxonomy exact: **True**
- Image correct: **True** - The chart data and omission state match the essay, and the PNG is readable.
- Image: [generated_images/pie_key_feature_omission_3.png](generated_images/pie_key_feature_omission_3.png)

Essay:

The chart divides average Canadian household expenditure in 2024 into six percentage shares.

Overall, the six shares were unevenly distributed, with clear differences between larger and smaller items.

A share of 17% went to Transport. A share of 10% went to Utilities. The proportion spent on Food was 21%. Housing accounted for 32% of expenditure. Households allocated 12% of their spending to Leisure.

These proportions show the different amounts of attention given to the reported spending items.

## Remaining failures

No failures occurred in this held-out batch.