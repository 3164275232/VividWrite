# VividWrite Randomized Taxonomy Robustness Report

## Protocol

- Frozen manifest SHA-256: `4a2c2d4ad67894ecb754603893c3e9abac7ca4651ab567c142c87b2b7b45f2ba`
- Fixed random seed: `20260812`
- Cases: 45 (3 chart types x 5 taxonomy classes x 3 independently varied essays)
- Randomized before inference: target entity/period, error magnitude, detail order, introduction, overview and value sentence templates.
- Workflow: cached DePlot output from each real chart -> DeepSeek alignment -> local validation -> taxonomy -> Vega-Lite PNG.
- No essay was changed after its output was observed.
- Single-period pie trend cases expect `N/A`, because a one-year pie has no temporal direction to verify.

## Summary

| Chart type | Cases | Exact taxonomy result | Data-faithful PNG |
| --- | ---: | ---: | ---: |
| Bar | 15 | 15/15 | 15/15 |
| Line | 15 | 7/15 | 6/15 |
| Pie | 15 | 13/15 | 13/15 |

Manual visual assessment: {'Correct': 20, 'Partially correct': 11, 'Incorrect': 11, 'Correct for N/A': 3}.

`Partially correct` means the PNG is readable and its numeric data match the essay, but a false trend or ranking statement is not visually encoded; the taxonomy panel is required to expose it.

## Per-case results

### Bar chart

#### bar_value_inaccuracy_1 - PASS

- Expected taxonomy: **Value Inaccuracy**
- Actual taxonomy: **Value Inaccuracy**
- Image assessment: **Correct** - The rendered chart matches the values and omissions stated in the essay.
- Image: [generated_images/bar_value_inaccuracy_1.png](generated_images/bar_value_inaccuracy_1.png)

Essay:

The grouped bars show the share of households that recycled in Bristol, Leeds, Liverpool, Manchester and Sheffield in 2015 and 2020.

Overall, the distribution changed across the two observations, and the five locations remained separated by noticeable margins.

In 2020, Sheffield registered 51%. In 2015, Sheffield registered 38%. For 2015, the rate reported for Leeds stood at 35%. In 2020, Liverpool registered 39%. In 2020, Bristol registered 66%. Manchester's figure in 2020 was 46%. Bristol's figure in 2015 was 42%. For 2020, the rate reported for Leeds stood at 48%. In 2015, Liverpool registered 28%. Manchester's figure in 2015 was 31%.

These percentages allow both changes over time and differences between places to be compared directly.

#### bar_value_inaccuracy_2 - PASS

- Expected taxonomy: **Value Inaccuracy**
- Actual taxonomy: **Value Inaccuracy**
- Image assessment: **Correct** - The rendered chart matches the values and omissions stated in the essay.
- Image: [generated_images/bar_value_inaccuracy_2.png](generated_images/bar_value_inaccuracy_2.png)

Essay:

The grouped bars show the share of households that recycled in Bristol, Leeds, Liverpool, Manchester and Sheffield in 2015 and 2020.

Overall, the distribution changed across the two observations, and the five locations remained separated by noticeable margins.

Bristol's figure in 2015 was 42%. In 2015, Liverpool registered 28%. Leeds's figure in 2015 was 35%. In 2020, Bristol registered 55%. For 2015, the rate reported for Manchester stood at 39%. In 2015, Sheffield registered 38%. For 2020, the rate reported for Manchester stood at 46%. For 2020, the rate reported for Liverpool stood at 39%. For 2020, the rate reported for Leeds stood at 48%. In 2020, Sheffield registered 51%.

Taken together, the observations provide a compact comparison of local recycling behaviour.

#### bar_value_inaccuracy_3 - PASS

- Expected taxonomy: **Value Inaccuracy**
- Actual taxonomy: **Value Inaccuracy**
- Image assessment: **Correct** - The rendered chart matches the values and omissions stated in the essay.
- Image: [generated_images/bar_value_inaccuracy_3.png](generated_images/bar_value_inaccuracy_3.png)

Essay:

The chart presents household recycling rates for five cities in the United Kingdom at two points in time, 2015 and 2020.

Overall, there were clear differences between the cities, while the second observation generally occupied a higher part of the scale.

Leeds's figure in 2020 was 48%. For 2015, the rate reported for Bristol stood at 42%. For 2015, the rate reported for Manchester stood at 37%. For 2015, the rate reported for Liverpool stood at 28%. In 2020, Sheffield registered 51%. Leeds's figure in 2015 was 35%. Bristol's figure in 2020 was 55%. Sheffield's figure in 2015 was 38%. In 2020, Liverpool registered 39%. For 2020, the rate reported for Manchester stood at 46%.

The data therefore show measurable variation rather than a uniform pattern across the country.

#### bar_entity_misalignment_1 - PASS

- Expected taxonomy: **Entity Misalignment**
- Actual taxonomy: **Entity Misalignment**
- Image assessment: **Correct** - The rendered chart matches the values and omissions stated in the essay.
- Image: [generated_images/bar_entity_misalignment_1.png](generated_images/bar_entity_misalignment_1.png)

Essay:

The chart presents household recycling rates for five cities in the United Kingdom at two points in time, 2015 and 2020.

Overall, there were clear differences between the cities, while the second observation generally occupied a higher part of the scale.

In 2015, Liverpool registered 28%. In 2020, Bristol registered 55%. Manchester's figure in 2015 was 31%. Bristol's figure in 2015 was 42%. For 2020, the rate reported for Leeds stood at 48%. Sheffield's figure in 2020 was 39%. In 2020, Liverpool registered 51%. Sheffield's figure in 2015 was 38%. Manchester's figure in 2020 was 46%. Leeds's figure in 2015 was 35%.

Taken together, the observations provide a compact comparison of local recycling behaviour.

#### bar_entity_misalignment_2 - PASS

- Expected taxonomy: **Entity Misalignment**
- Actual taxonomy: **Entity Misalignment**
- Image assessment: **Correct** - The rendered chart matches the values and omissions stated in the essay.
- Image: [generated_images/bar_entity_misalignment_2.png](generated_images/bar_entity_misalignment_2.png)

Essay:

The grouped bars show the share of households that recycled in Bristol, Leeds, Liverpool, Manchester and Sheffield in 2015 and 2020.

Overall, the figures varied by location and the distance between neighbouring cities was often modest.

Liverpool's figure in 2020 was 39%. Leeds's figure in 2015 was 35%. In 2015, Bristol registered 42%. For 2015, the rate reported for Liverpool stood at 38%. Manchester's figure in 2015 was 31%. In 2020, Manchester registered 46%. In 2020, Leeds registered 48%. In 2015, Sheffield registered 28%. In 2020, Bristol registered 55%. For 2020, the rate reported for Sheffield stood at 51%.

The data therefore show measurable variation rather than a uniform pattern across the country.

#### bar_entity_misalignment_3 - PASS

- Expected taxonomy: **Entity Misalignment**
- Actual taxonomy: **Entity Misalignment**
- Image assessment: **Correct** - The rendered chart matches the values and omissions stated in the essay.
- Image: [generated_images/bar_entity_misalignment_3.png](generated_images/bar_entity_misalignment_3.png)

Essay:

The grouped bars show the share of households that recycled in Bristol, Leeds, Liverpool, Manchester and Sheffield in 2015 and 2020.

Overall, the figures varied by location and the distance between neighbouring cities was often modest.

Leeds's figure in 2020 was 48%. Bristol's figure in 2020 was 39%. Sheffield's figure in 2020 was 51%. Leeds's figure in 2015 was 35%. In 2015, Bristol registered 42%. For 2015, the rate reported for Manchester stood at 31%. In 2020, Liverpool registered 55%. In 2015, Liverpool registered 28%. In 2015, Sheffield registered 38%. For 2020, the rate reported for Manchester stood at 46%.

Taken together, the observations provide a compact comparison of local recycling behaviour.

#### bar_trend_direction_error_1 - PASS

- Expected taxonomy: **Trend Direction Error**
- Actual taxonomy: **Trend Direction Error**
- Image assessment: **Partially correct** - The stated numeric data are rendered correctly, but a false trend/rank sentence does not alter the chart, so the visual alone does not expose that semantic error.
- Image: [generated_images/bar_trend_direction_error_1.png](generated_images/bar_trend_direction_error_1.png)

Essay:

The bar chart compares the percentages of households recycling waste in five British cities in 2015 and 2020.

Overall, Liverpool followed a downward trend from 2015 to 2020, against a background of variation between locations.

Manchester's figure in 2020 was 46%. For 2015, the rate reported for Bristol stood at 42%. For 2015, the rate reported for Manchester stood at 31%. Sheffield's figure in 2020 was 51%. For 2020, the rate reported for Leeds stood at 48%. Liverpool's figure in 2020 was 39%. Bristol's figure in 2020 was 55%. For 2015, the rate reported for Liverpool stood at 28%. For 2015, the rate reported for Leeds stood at 35%. In 2015, Sheffield registered 38%.

Taken together, the observations provide a compact comparison of local recycling behaviour.

#### bar_trend_direction_error_2 - PASS

- Expected taxonomy: **Trend Direction Error**
- Actual taxonomy: **Trend Direction Error**
- Image assessment: **Partially correct** - The stated numeric data are rendered correctly, but a false trend/rank sentence does not alter the chart, so the visual alone does not expose that semantic error.
- Image: [generated_images/bar_trend_direction_error_2.png](generated_images/bar_trend_direction_error_2.png)

Essay:

The grouped bars show the share of households that recycled in Bristol, Leeds, Liverpool, Manchester and Sheffield in 2015 and 2020.

Overall, Manchester decreased over the period, while the chart continued to show marked differences between the five cities.

For 2020, the rate reported for Manchester stood at 46%. For 2015, the rate reported for Leeds stood at 35%. Leeds's figure in 2020 was 48%. In 2015, Manchester registered 31%. Bristol's figure in 2015 was 42%. For 2020, the rate reported for Sheffield stood at 51%. Bristol's figure in 2020 was 55%. For 2015, the rate reported for Sheffield stood at 38%. For 2020, the rate reported for Liverpool stood at 39%. Liverpool's figure in 2015 was 28%.

Taken together, the observations provide a compact comparison of local recycling behaviour.

#### bar_trend_direction_error_3 - PASS

- Expected taxonomy: **Trend Direction Error**
- Actual taxonomy: **Trend Direction Error**
- Image assessment: **Partially correct** - The stated numeric data are rendered correctly, but a false trend/rank sentence does not alter the chart, so the visual alone does not expose that semantic error.
- Image: [generated_images/bar_trend_direction_error_3.png](generated_images/bar_trend_direction_error_3.png)

Essay:

The grouped bars show the share of households that recycled in Bristol, Leeds, Liverpool, Manchester and Sheffield in 2015 and 2020.

Overall, Bristol decreased over the period, while the chart continued to show marked differences between the five cities.

Bristol's figure in 2015 was 42%. In 2015, Liverpool registered 28%. For 2015, the rate reported for Manchester stood at 31%. Liverpool's figure in 2020 was 39%. Bristol's figure in 2020 was 55%. For 2015, the rate reported for Leeds stood at 35%. For 2020, the rate reported for Manchester stood at 46%. For 2015, the rate reported for Sheffield stood at 38%. In 2020, Leeds registered 48%. For 2020, the rate reported for Sheffield stood at 51%.

The data therefore show measurable variation rather than a uniform pattern across the country.

#### bar_comparison_ranking_error_1 - PASS

- Expected taxonomy: **Comparison Ranking Error**
- Actual taxonomy: **Comparison Ranking Error**
- Image assessment: **Partially correct** - The stated numeric data are rendered correctly, but a false trend/rank sentence does not alter the chart, so the visual alone does not expose that semantic error.
- Image: [generated_images/bar_comparison_ranking_error_1.png](generated_images/bar_comparison_ranking_error_1.png)

Essay:

The grouped bars show the share of households that recycled in Bristol, Leeds, Liverpool, Manchester and Sheffield in 2015 and 2020.

Overall, Manchester recorded the highest recycling rate in 2020, while the cities remained separated by clear differences.

Liverpool's figure in 2015 was 28%. For 2015, the rate reported for Leeds stood at 35%. Leeds's figure in 2020 was 48%. Manchester's figure in 2020 was 46%. Sheffield's figure in 2020 was 51%. Manchester's figure in 2015 was 31%. For 2015, the rate reported for Sheffield stood at 38%. Liverpool's figure in 2020 was 39%. For 2015, the rate reported for Bristol stood at 42%. Bristol's figure in 2020 was 55%.

These percentages allow both changes over time and differences between places to be compared directly.

#### bar_comparison_ranking_error_2 - PASS

- Expected taxonomy: **Comparison Ranking Error**
- Actual taxonomy: **Comparison Ranking Error**
- Image assessment: **Partially correct** - The stated numeric data are rendered correctly, but a false trend/rank sentence does not alter the chart, so the visual alone does not expose that semantic error.
- Image: [generated_images/bar_comparison_ranking_error_2.png](generated_images/bar_comparison_ranking_error_2.png)

Essay:

The grouped bars show the share of households that recycled in Bristol, Leeds, Liverpool, Manchester and Sheffield in 2015 and 2020.

Overall, Leeds recorded the highest recycling rate in 2015, while the cities remained separated by clear differences.

Sheffield's figure in 2020 was 51%. In 2015, Bristol registered 42%. For 2015, the rate reported for Leeds stood at 35%. In 2020, Bristol registered 55%. For 2015, the rate reported for Sheffield stood at 38%. Liverpool's figure in 2020 was 39%. For 2015, the rate reported for Manchester stood at 31%. For 2020, the rate reported for Manchester stood at 46%. Liverpool's figure in 2015 was 28%. For 2020, the rate reported for Leeds stood at 48%.

The data therefore show measurable variation rather than a uniform pattern across the country.

#### bar_comparison_ranking_error_3 - PASS

- Expected taxonomy: **Comparison Ranking Error**
- Actual taxonomy: **Comparison Ranking Error**
- Image assessment: **Partially correct** - The stated numeric data are rendered correctly, but a false trend/rank sentence does not alter the chart, so the visual alone does not expose that semantic error.
- Image: [generated_images/bar_comparison_ranking_error_3.png](generated_images/bar_comparison_ranking_error_3.png)

Essay:

The chart presents household recycling rates for five cities in the United Kingdom at two points in time, 2015 and 2020.

Overall, Sheffield recorded the lowest recycling rate in 2020, while the cities remained separated by clear differences.

Leeds's figure in 2015 was 35%. In 2020, Leeds registered 48%. For 2020, the rate reported for Bristol stood at 55%. In 2015, Liverpool registered 28%. Sheffield's figure in 2015 was 38%. For 2015, the rate reported for Manchester stood at 31%. Sheffield's figure in 2020 was 51%. Manchester's figure in 2020 was 46%. For 2020, the rate reported for Liverpool stood at 39%. Bristol's figure in 2015 was 42%.

These percentages allow both changes over time and differences between places to be compared directly.

#### bar_key_feature_omission_1 - PASS

- Expected taxonomy: **Key Feature Omission**
- Actual taxonomy: **Key Feature Omission**
- Image assessment: **Correct** - The rendered chart matches the values and omissions stated in the essay.
- Image: [generated_images/bar_key_feature_omission_1.png](generated_images/bar_key_feature_omission_1.png)

Essay:

The grouped bars show the share of households that recycled in Bristol, Leeds, Liverpool, Manchester and Sheffield in 2015 and 2020.

Overall, there were clear differences between the cities, while the second observation generally occupied a higher part of the scale.

In 2015, Manchester registered 31%. Leeds's figure in 2015 was 35%. Leeds's figure in 2020 was 48%. In 2015, Sheffield registered 38%. In 2020, Manchester registered 46%. Bristol's figure in 2015 was 42%. For 2020, the rate reported for Sheffield stood at 51%. Bristol's figure in 2020 was 55%.

These percentages allow both changes over time and differences between places to be compared directly.

#### bar_key_feature_omission_2 - PASS

- Expected taxonomy: **Key Feature Omission**
- Actual taxonomy: **Key Feature Omission**
- Image assessment: **Correct** - The rendered chart matches the values and omissions stated in the essay.
- Image: [generated_images/bar_key_feature_omission_2.png](generated_images/bar_key_feature_omission_2.png)

Essay:

The chart presents household recycling rates for five cities in the United Kingdom at two points in time, 2015 and 2020.

Overall, the figures varied by location and the distance between neighbouring cities was often modest.

In 2015, Bristol registered 42%. Liverpool's figure in 2020 was 39%. Manchester's figure in 2020 was 46%. For 2015, the rate reported for Manchester stood at 31%. Liverpool's figure in 2015 was 28%. In 2020, Leeds registered 48%. In 2015, Leeds registered 35%. For 2020, the rate reported for Bristol stood at 55%.

Taken together, the observations provide a compact comparison of local recycling behaviour.

#### bar_key_feature_omission_3 - PASS

- Expected taxonomy: **Key Feature Omission**
- Actual taxonomy: **Key Feature Omission**
- Image assessment: **Correct** - The rendered chart matches the values and omissions stated in the essay.
- Image: [generated_images/bar_key_feature_omission_3.png](generated_images/bar_key_feature_omission_3.png)

Essay:

The bar chart compares the percentages of households recycling waste in five British cities in 2015 and 2020.

Overall, there were clear differences between the cities, while the second observation generally occupied a higher part of the scale.

For 2020, the rate reported for Leeds stood at 48%. Liverpool's figure in 2015 was 28%. Liverpool's figure in 2020 was 39%. For 2020, the rate reported for Bristol stood at 55%. Bristol's figure in 2015 was 42%. Sheffield's figure in 2015 was 38%. For 2020, the rate reported for Sheffield stood at 51%. Leeds's figure in 2015 was 35%.

Taken together, the observations provide a compact comparison of local recycling behaviour.

### Line chart

#### line_value_inaccuracy_1 - FAIL

- Expected taxonomy: **Value Inaccuracy**
- Actual taxonomy: **Value Inaccuracy, Key Feature Omission**
- Image assessment: **Incorrect** - Metro/2010: expected 0.8, rendered None; Metro/2020: expected 1.9, rendered None
- Image: [generated_images/line_value_inaccuracy_1.png](generated_images/line_value_inaccuracy_1.png)
- Failure analysis: One or more 'at the beginning/end' endpoint phrases were not mapped to explicit years. The intended class was usually detected, but extra endpoint omissions were reported and the generated line lost points.

Essay:

The graph plots the number of passengers using three forms of public transport on an average day from 2010 to 2020.

Overall, the lines did not remain in their initial order, and the gap between services changed over time.

In 2010, Bus served 1.8 million passengers per day, compared with 1.7 million in 2020. In 2010, Rail served 1.1 million passengers per day, compared with 2.2 million in 2020. The figures for Metro were 0.8 million at the beginning and 1.9 million at the end. In 2016, the figure for Bus was 1.6 million. At 2016, Metro stood at 1.5 million passengers. In 2016, the figure for Rail was 1.8 million.

The intermediate observations help to show how the ordering developed rather than only giving two isolated totals.

#### line_value_inaccuracy_2 - PASS

- Expected taxonomy: **Value Inaccuracy**
- Actual taxonomy: **Value Inaccuracy**
- Image assessment: **Correct** - The rendered chart matches the values and omissions stated in the essay.
- Image: [generated_images/line_value_inaccuracy_2.png](generated_images/line_value_inaccuracy_2.png)

Essay:

The line graph compares average daily passenger numbers for bus, rail and metro services between 2010 and 2020, measured in millions.

Overall, passenger use was distributed differently across the three modes by the end of the period.

Metro carried 0.8 million passengers in 2010 and 1.9 million in 2020. Bus carried 1.5 million passengers in 2010 and 1.3 million in 2020. Rail carried 1.1 million passengers in 2010 and 2.2 million in 2020. At 2018, Rail stood at 2.0 million passengers. In 2018, the figure for Bus was 1.5 million. Metro recorded 1.7 million daily users in 2018.

These figures make the changing balance among the transport services visible across the decade.

#### line_value_inaccuracy_3 - FAIL

- Expected taxonomy: **Value Inaccuracy**
- Actual taxonomy: **Key Feature Omission**
- Image assessment: **Incorrect** - Bus/2010: expected 1.8, rendered None; Bus/2020: expected 1.3, rendered None; Rail/2010: expected 0.8, rendered None; Rail/2020: expected 2.2, rendered None
- Image: [generated_images/line_value_inaccuracy_3.png](generated_images/line_value_inaccuracy_3.png)
- Failure analysis: The phrase 'at the beginning/end' was not reliably aligned to 2010/2020 for Bus and Rail. The wrong Rail value was therefore dropped and converted into endpoint omissions.

Essay:

The graph plots the number of passengers using three forms of public transport on an average day from 2010 to 2020.

Overall, the lines did not remain in their initial order, and the gap between services changed over time.

The figures for Bus were 1.8 million at the beginning and 1.3 million at the end. In 2010, Metro served 0.8 million passengers per day, compared with 1.9 million in 2020. The figures for Rail were 0.8 million at the beginning and 2.2 million at the end. Rail recorded 2.0 million daily users in 2018. Bus recorded 1.5 million daily users in 2018. In 2018, the figure for Metro was 1.7 million.

These figures make the changing balance among the transport services visible across the decade.

#### line_entity_misalignment_1 - PASS

- Expected taxonomy: **Entity Misalignment**
- Actual taxonomy: **Entity Misalignment**
- Image assessment: **Correct** - The rendered chart matches the values and omissions stated in the essay.
- Image: [generated_images/line_entity_misalignment_1.png](generated_images/line_entity_misalignment_1.png)

Essay:

The line graph compares average daily passenger numbers for bus, rail and metro services between 2010 and 2020, measured in millions.

Overall, the lines did not remain in their initial order, and the gap between services changed over time.

In 2010, Bus served 1.8 million passengers per day, compared with 1.3 million in 2020. Rail carried 1.1 million passengers in 2010 and 2.2 million in 2020. In 2010, Metro served 0.8 million passengers per day, compared with 1.9 million in 2020. At 2018, Bus stood at 2.0 million passengers. Rail recorded 1.5 million daily users in 2018. In 2018, the figure for Metro was 1.7 million.

These figures make the changing balance among the transport services visible across the decade.

#### line_entity_misalignment_2 - FAIL

- Expected taxonomy: **Entity Misalignment**
- Actual taxonomy: **Entity Misalignment, Key Feature Omission**
- Image assessment: **Incorrect** - Bus/2010: expected 1.8, rendered None; Bus/2020: expected 1.3, rendered None; Rail/2010: expected 1.1, rendered None; Rail/2020: expected 2.2, rendered None; Metro/2010: expected 0.8, rendered None; Metro/2020: expected 1.9, rendered None
- Image: [generated_images/line_entity_misalignment_2.png](generated_images/line_entity_misalignment_2.png)
- Failure analysis: One or more 'at the beginning/end' endpoint phrases were not mapped to explicit years. The intended class was usually detected, but extra endpoint omissions were reported and the generated line lost points.

Essay:

The line graph compares average daily passenger numbers for bus, rail and metro services between 2010 and 2020, measured in millions.

Overall, the lines did not remain in their initial order, and the gap between services changed over time.

The figures for Metro were 0.8 million at the beginning and 1.9 million at the end. The figures for Rail were 1.1 million at the beginning and 2.2 million at the end. The figures for Bus were 1.8 million at the beginning and 1.3 million at the end. In 2016, the figure for Metro was 1.5 million. In 2016, the figure for Bus was 1.8 million. Rail recorded 1.6 million daily users in 2016.

The recorded points provide enough detail to compare the services at both the beginning and the end.

#### line_entity_misalignment_3 - FAIL

- Expected taxonomy: **Entity Misalignment**
- Actual taxonomy: **Entity Misalignment, Key Feature Omission**
- Image assessment: **Incorrect** - Bus/2010: expected 1.8, rendered None; Bus/2020: expected 1.3, rendered None; Rail/2010: expected 1.1, rendered None; Rail/2020: expected 2.2, rendered None; Metro/2010: expected 0.8, rendered None; Metro/2020: expected 1.9, rendered None
- Image: [generated_images/line_entity_misalignment_3.png](generated_images/line_entity_misalignment_3.png)
- Failure analysis: One or more 'at the beginning/end' endpoint phrases were not mapped to explicit years. The intended class was usually detected, but extra endpoint omissions were reported and the generated line lost points.

Essay:

The line graph compares average daily passenger numbers for bus, rail and metro services between 2010 and 2020, measured in millions.

Overall, passenger use was distributed differently across the three modes by the end of the period.

The figures for Metro were 0.8 million at the beginning and 1.9 million at the end. The figures for Rail were 1.1 million at the beginning and 2.2 million at the end. The figures for Bus were 1.8 million at the beginning and 1.3 million at the end. At 2018, Rail stood at 2.0 million passengers. Bus recorded 1.7 million daily users in 2018. At 2018, Metro stood at 1.5 million passengers.

The intermediate observations help to show how the ordering developed rather than only giving two isolated totals.

#### line_trend_direction_error_1 - FAIL

- Expected taxonomy: **Trend Direction Error**
- Actual taxonomy: **Trend Direction Error, Key Feature Omission**
- Image assessment: **Incorrect** - Rail/2010: expected 1.1, rendered None; Rail/2020: expected 2.2, rendered None
- Image: [generated_images/line_trend_direction_error_1.png](generated_images/line_trend_direction_error_1.png)
- Failure analysis: One or more 'at the beginning/end' endpoint phrases were not mapped to explicit years. The intended class was usually detected, but extra endpoint omissions were reported and the generated line lost points.

Essay:

The line chart illustrates changes in daily bus, rail and metro use over the period 2010-2020, with figures given in millions.

Overall, Rail fell over the period, while the relative positions of the three services changed during the decade.

Bus carried 1.8 million passengers in 2010 and 1.3 million in 2020. Metro carried 0.8 million passengers in 2010 and 1.9 million in 2020. The figures for Rail were 1.1 million at the beginning and 2.2 million at the end. At 2014, Metro stood at 1.2 million passengers. In 2014, the figure for Rail was 1.5 million. Bus recorded 1.7 million daily users in 2014.

These figures make the changing balance among the transport services visible across the decade.

#### line_trend_direction_error_2 - PASS

- Expected taxonomy: **Trend Direction Error**
- Actual taxonomy: **Trend Direction Error**
- Image assessment: **Partially correct** - The stated numeric data are rendered correctly, but a false trend/rank sentence does not alter the chart, so the visual alone does not expose that semantic error.
- Image: [generated_images/line_trend_direction_error_2.png](generated_images/line_trend_direction_error_2.png)

Essay:

The line graph compares average daily passenger numbers for bus, rail and metro services between 2010 and 2020, measured in millions.

Overall, Rail declined over the period, while the relative positions of the three services changed during the decade.

Rail carried 1.1 million passengers in 2010 and 2.2 million in 2020. In 2010, Bus served 1.8 million passengers per day, compared with 1.3 million in 2020. Metro carried 0.8 million passengers in 2010 and 1.9 million in 2020. In 2016, the figure for Rail was 1.8 million. At 2016, Metro stood at 1.5 million passengers. At 2016, Bus stood at 1.6 million passengers.

The recorded points provide enough detail to compare the services at both the beginning and the end.

#### line_trend_direction_error_3 - FAIL

- Expected taxonomy: **Trend Direction Error**
- Actual taxonomy: **Trend Direction Error, Key Feature Omission**
- Image assessment: **Incorrect** - Rail/2010: expected 1.1, rendered None; Rail/2020: expected 2.2, rendered None
- Image: [generated_images/line_trend_direction_error_3.png](generated_images/line_trend_direction_error_3.png)
- Failure analysis: One or more 'at the beginning/end' endpoint phrases were not mapped to explicit years. The intended class was usually detected, but extra endpoint omissions were reported and the generated line lost points.

Essay:

The line graph compares average daily passenger numbers for bus, rail and metro services between 2010 and 2020, measured in millions.

Overall, Bus climbed over the period, while the relative positions of the three services changed during the decade.

In 2010, Bus served 1.8 million passengers per day, compared with 1.3 million in 2020. The figures for Rail were 1.1 million at the beginning and 2.2 million at the end. In 2010, Metro served 0.8 million passengers per day, compared with 1.9 million in 2020. In 2016, the figure for Metro was 1.5 million. In 2016, the figure for Bus was 1.6 million. At 2016, Rail stood at 1.8 million passengers.

The intermediate observations help to show how the ordering developed rather than only giving two isolated totals.

#### line_comparison_ranking_error_1 - PASS

- Expected taxonomy: **Comparison Ranking Error**
- Actual taxonomy: **Comparison Ranking Error**
- Image assessment: **Partially correct** - The stated numeric data are rendered correctly, but a false trend/rank sentence does not alter the chart, so the visual alone does not expose that semantic error.
- Image: [generated_images/line_comparison_ranking_error_1.png](generated_images/line_comparison_ranking_error_1.png)

Essay:

The graph plots the number of passengers using three forms of public transport on an average day from 2010 to 2020.

Overall, Metro was the highest transport mode in 2020, while the ordering of the three services changed elsewhere in the period.

Bus carried 1.8 million passengers in 2010 and 1.3 million in 2020. In 2010, Rail served 1.1 million passengers per day, compared with 2.2 million in 2020. Metro carried 0.8 million passengers in 2010 and 1.9 million in 2020. In 2014, the figure for Metro was 1.2 million. In 2014, the figure for Rail was 1.5 million. Bus recorded 1.7 million daily users in 2014.

The intermediate observations help to show how the ordering developed rather than only giving two isolated totals.

#### line_comparison_ranking_error_2 - FAIL

- Expected taxonomy: **Comparison Ranking Error**
- Actual taxonomy: **Comparison Ranking Error, Key Feature Omission**
- Image assessment: **Incorrect** - Metro/2010: expected 0.8, rendered None; Metro/2020: expected 1.9, rendered None
- Image: [generated_images/line_comparison_ranking_error_2.png](generated_images/line_comparison_ranking_error_2.png)
- Failure analysis: One or more 'at the beginning/end' endpoint phrases were not mapped to explicit years. The intended class was usually detected, but extra endpoint omissions were reported and the generated line lost points.

Essay:

The graph plots the number of passengers using three forms of public transport on an average day from 2010 to 2020.

Overall, Metro was the highest transport mode in 2010, while the ordering of the three services changed elsewhere in the period.

In 2010, Rail served 1.1 million passengers per day, compared with 2.2 million in 2020. The figures for Metro were 0.8 million at the beginning and 1.9 million at the end. Bus carried 1.8 million passengers in 2010 and 1.3 million in 2020. Rail recorded 1.8 million daily users in 2016. At 2016, Metro stood at 1.5 million passengers. Bus recorded 1.6 million daily users in 2016.

The recorded points provide enough detail to compare the services at both the beginning and the end.

#### line_comparison_ranking_error_3 - FAIL

- Expected taxonomy: **Comparison Ranking Error**
- Actual taxonomy: **Comparison Ranking Error, Key Feature Omission**
- Image assessment: **Incorrect** - Bus/2010: expected 1.8, rendered None; Bus/2020: expected 1.3, rendered None
- Image: [generated_images/line_comparison_ranking_error_3.png](generated_images/line_comparison_ranking_error_3.png)
- Failure analysis: One or more 'at the beginning/end' endpoint phrases were not mapped to explicit years. The intended class was usually detected, but extra endpoint omissions were reported and the generated line lost points.

Essay:

The line graph compares average daily passenger numbers for bus, rail and metro services between 2010 and 2020, measured in millions.

Overall, Metro was the highest transport mode in 2020, while the ordering of the three services changed elsewhere in the period.

The figures for Bus were 1.8 million at the beginning and 1.3 million at the end. In 2010, Rail served 1.1 million passengers per day, compared with 2.2 million in 2020. Metro carried 0.8 million passengers in 2010 and 1.9 million in 2020. At 2014, Bus stood at 1.7 million passengers. In 2014, the figure for Rail was 1.5 million. Metro recorded 1.2 million daily users in 2014.

The intermediate observations help to show how the ordering developed rather than only giving two isolated totals.

#### line_key_feature_omission_1 - PASS

- Expected taxonomy: **Key Feature Omission**
- Actual taxonomy: **Key Feature Omission**
- Image assessment: **Incorrect** - Bus/2010: expected 1.8, rendered None; Bus/2020: expected 1.3, rendered None
- Image: [generated_images/line_key_feature_omission_1.png](generated_images/line_key_feature_omission_1.png)
- Failure analysis: One or more 'at the beginning/end' endpoint phrases were not mapped to explicit years. The intended class was usually detected, but extra endpoint omissions were reported and the generated line lost points.

Essay:

The graph plots the number of passengers using three forms of public transport on an average day from 2010 to 2020.

Overall, the three services followed visibly different paths and their relative positions changed during the decade.

In 2010, Metro served 0.8 million passengers per day, compared with 1.9 million in 2020. The figures for Bus were 1.8 million at the beginning and 1.3 million at the end. In 2012, the figure for Bus was 1.9 million. Metro recorded 1.0 million daily users in 2012.

These figures make the changing balance among the transport services visible across the decade.

#### line_key_feature_omission_2 - PASS

- Expected taxonomy: **Key Feature Omission**
- Actual taxonomy: **Key Feature Omission**
- Image assessment: **Correct** - The rendered chart matches the values and omissions stated in the essay.
- Image: [generated_images/line_key_feature_omission_2.png](generated_images/line_key_feature_omission_2.png)

Essay:

The graph plots the number of passengers using three forms of public transport on an average day from 2010 to 2020.

Overall, passenger use was distributed differently across the three modes by the end of the period.

Metro carried 0.8 million passengers in 2010 and 1.9 million in 2020. Rail carried 1.1 million passengers in 2010 and 2.2 million in 2020. In 2016, the figure for Metro was 1.5 million. In 2016, the figure for Rail was 1.8 million.

The intermediate observations help to show how the ordering developed rather than only giving two isolated totals.

#### line_key_feature_omission_3 - PASS

- Expected taxonomy: **Key Feature Omission**
- Actual taxonomy: **Key Feature Omission**
- Image assessment: **Correct** - The rendered chart matches the values and omissions stated in the essay.
- Image: [generated_images/line_key_feature_omission_3.png](generated_images/line_key_feature_omission_3.png)

Essay:

The line graph compares average daily passenger numbers for bus, rail and metro services between 2010 and 2020, measured in millions.

Overall, the three services followed visibly different paths and their relative positions changed during the decade.

In 2010, Metro served 0.8 million passengers per day, compared with 1.9 million in 2020. Rail carried 1.1 million passengers in 2010 and 2.2 million in 2020. In 2016, the figure for Metro was 1.5 million. In 2016, the figure for Rail was 1.8 million.

The intermediate observations help to show how the ordering developed rather than only giving two isolated totals.

### Pie chart

#### pie_value_inaccuracy_1 - PASS

- Expected taxonomy: **Value Inaccuracy**
- Actual taxonomy: **Value Inaccuracy**
- Image assessment: **Correct** - The rendered chart matches the values and omissions stated in the essay.
- Image: [generated_images/pie_value_inaccuracy_1.png](generated_images/pie_value_inaccuracy_1.png)

Essay:

The chart shows how an average household in Canada allocated its spending in 2024.

Overall, a few categories accounted for substantial portions of the budget, while the remaining shares were more limited.

Households devoted 12% of expenditure to Leisure. Utilities represented 10% of the budget. Other represented 8% of the budget. Households devoted 21% of expenditure to Food. The share allocated to Housing was 37%. Transport represented 17% of the budget.

This distribution makes it possible to compare major commitments with smaller items of expenditure.

#### pie_value_inaccuracy_2 - PASS

- Expected taxonomy: **Value Inaccuracy**
- Actual taxonomy: **Value Inaccuracy**
- Image assessment: **Correct** - The rendered chart matches the values and omissions stated in the essay.
- Image: [generated_images/pie_value_inaccuracy_2.png](generated_images/pie_value_inaccuracy_2.png)

Essay:

The chart shows how an average household in Canada allocated its spending in 2024.

Overall, a few categories accounted for substantial portions of the budget, while the remaining shares were more limited.

The share allocated to Other was 8%. The share allocated to Utilities was 10%. The share allocated to Leisure was 8%. Food represented 21% of the budget. Households devoted 32% of expenditure to Housing. Transport represented 17% of the budget.

This distribution makes it possible to compare major commitments with smaller items of expenditure.

#### pie_value_inaccuracy_3 - PASS

- Expected taxonomy: **Value Inaccuracy**
- Actual taxonomy: **Value Inaccuracy**
- Image assessment: **Correct** - The rendered chart matches the values and omissions stated in the essay.
- Image: [generated_images/pie_value_inaccuracy_3.png](generated_images/pie_value_inaccuracy_3.png)

Essay:

The pie chart breaks down average Canadian household expenditure in 2024 across six spending categories.

Overall, spending was spread unevenly, with several medium-sized components and a smaller group of minor items.

The share allocated to Food was 17%. Households devoted 10% of expenditure to Utilities. Households devoted 8% of expenditure to Other. Transport represented 17% of the budget. Households devoted 32% of expenditure to Housing. The share allocated to Leisure was 12%.

This distribution makes it possible to compare major commitments with smaller items of expenditure.

#### pie_entity_misalignment_1 - PASS

- Expected taxonomy: **Entity Misalignment**
- Actual taxonomy: **Entity Misalignment**
- Image assessment: **Correct** - The rendered chart matches the values and omissions stated in the essay.
- Image: [generated_images/pie_entity_misalignment_1.png](generated_images/pie_entity_misalignment_1.png)

Essay:

The circular chart presents the percentage distribution of Canadian household expenditure among six categories in 2024.

Overall, spending was spread unevenly, with several medium-sized components and a smaller group of minor items.

The share allocated to Leisure was 12%. Households devoted 10% of expenditure to Utilities. The share allocated to Food was 17%. Other represented 8% of the budget. Households devoted 32% of expenditure to Housing. Households devoted 21% of expenditure to Transport.

The proportions give a direct view of how the household budget was divided during the year.

#### pie_entity_misalignment_2 - PASS

- Expected taxonomy: **Entity Misalignment**
- Actual taxonomy: **Entity Misalignment**
- Image assessment: **Correct** - The rendered chart matches the values and omissions stated in the essay.
- Image: [generated_images/pie_entity_misalignment_2.png](generated_images/pie_entity_misalignment_2.png)

Essay:

The circular chart presents the percentage distribution of Canadian household expenditure among six categories in 2024.

Overall, spending was spread unevenly, with several medium-sized components and a smaller group of minor items.

Households devoted 21% of expenditure to Food. Households devoted 10% of expenditure to Utilities. Households devoted 8% of expenditure to Other. Leisure represented 17% of the budget. The share allocated to Transport was 12%. Housing represented 32% of the budget.

The proportions give a direct view of how the household budget was divided during the year.

#### pie_entity_misalignment_3 - PASS

- Expected taxonomy: **Entity Misalignment**
- Actual taxonomy: **Entity Misalignment**
- Image assessment: **Correct** - The rendered chart matches the values and omissions stated in the essay.
- Image: [generated_images/pie_entity_misalignment_3.png](generated_images/pie_entity_misalignment_3.png)

Essay:

The chart shows how an average household in Canada allocated its spending in 2024.

Overall, the household budget was divided into clearly unequal shares rather than being distributed evenly.

The share allocated to Transport was 17%. The share allocated to Food was 21%. Utilities represented 8% of the budget. The share allocated to Housing was 32%. Other represented 10% of the budget. Leisure represented 12% of the budget.

The proportions give a direct view of how the household budget was divided during the year.

#### pie_trend_direction_error_1 - PASS

- Expected taxonomy: **N/A: trend not applicable**
- Actual taxonomy: **None**
- Image assessment: **Correct for N/A** - The single-period pie is rendered correctly; no temporal trend can be encoded.
- Image: [generated_images/pie_trend_direction_error_1.png](generated_images/pie_trend_direction_error_1.png)

Essay:

The chart shows how an average household in Canada allocated its spending in 2024.

Overall, Other remained stable over the period, while expenditure was distributed unevenly across the six categories.

Households devoted 10% of expenditure to Utilities. Households devoted 21% of expenditure to Food. Other represented 8% of the budget. The share allocated to Transport was 17%. Housing represented 32% of the budget. Leisure represented 12% of the budget.

This distribution makes it possible to compare major commitments with smaller items of expenditure.

#### pie_trend_direction_error_2 - PASS

- Expected taxonomy: **N/A: trend not applicable**
- Actual taxonomy: **None**
- Image assessment: **Correct for N/A** - The single-period pie is rendered correctly; no temporal trend can be encoded.
- Image: [generated_images/pie_trend_direction_error_2.png](generated_images/pie_trend_direction_error_2.png)

Essay:

The circular chart presents the percentage distribution of Canadian household expenditure among six categories in 2024.

Overall, Other decreased over the period, while expenditure was distributed unevenly across the six categories.

Other represented 8% of the budget. Households devoted 21% of expenditure to Food. Utilities represented 10% of the budget. Leisure represented 12% of the budget. Households devoted 32% of expenditure to Housing. The share allocated to Transport was 17%.

The proportions give a direct view of how the household budget was divided during the year.

#### pie_trend_direction_error_3 - PASS

- Expected taxonomy: **N/A: trend not applicable**
- Actual taxonomy: **None**
- Image assessment: **Correct for N/A** - The single-period pie is rendered correctly; no temporal trend can be encoded.
- Image: [generated_images/pie_trend_direction_error_3.png](generated_images/pie_trend_direction_error_3.png)

Essay:

The pie chart breaks down average Canadian household expenditure in 2024 across six spending categories.

Overall, Housing increased over the period, while expenditure was distributed unevenly across the six categories.

Households devoted 32% of expenditure to Housing. Households devoted 21% of expenditure to Food. Transport represented 17% of the budget. The share allocated to Leisure was 12%. Households devoted 10% of expenditure to Utilities. Other represented 8% of the budget.

The proportions give a direct view of how the household budget was divided during the year.

#### pie_comparison_ranking_error_1 - PASS

- Expected taxonomy: **Comparison Ranking Error**
- Actual taxonomy: **Comparison Ranking Error**
- Image assessment: **Partially correct** - The stated numeric data are rendered correctly, but a false trend/rank sentence does not alter the chart, so the visual alone does not expose that semantic error.
- Image: [generated_images/pie_comparison_ranking_error_1.png](generated_images/pie_comparison_ranking_error_1.png)

Essay:

The pie chart breaks down average Canadian household expenditure in 2024 across six spending categories.

Overall, Utilities was the largest component of household expenditure, while the remaining categories occupied unequal shares.

Households devoted 32% of expenditure to Housing. Transport represented 17% of the budget. The share allocated to Utilities was 10%. Households devoted 21% of expenditure to Food. Other represented 8% of the budget. Households devoted 12% of expenditure to Leisure.

The proportions give a direct view of how the household budget was divided during the year.

#### pie_comparison_ranking_error_2 - PASS

- Expected taxonomy: **Comparison Ranking Error**
- Actual taxonomy: **Comparison Ranking Error**
- Image assessment: **Partially correct** - The stated numeric data are rendered correctly, but a false trend/rank sentence does not alter the chart, so the visual alone does not expose that semantic error.
- Image: [generated_images/pie_comparison_ranking_error_2.png](generated_images/pie_comparison_ranking_error_2.png)

Essay:

The chart shows how an average household in Canada allocated its spending in 2024.

Overall, Other was the largest component of household expenditure, while the remaining categories occupied unequal shares.

Households devoted 12% of expenditure to Leisure. Households devoted 21% of expenditure to Food. The share allocated to Housing was 32%. Other represented 8% of the budget. The share allocated to Utilities was 10%. Transport represented 17% of the budget.

Together, the listed components account for the complete household budget shown in the chart.

#### pie_comparison_ranking_error_3 - PASS

- Expected taxonomy: **Comparison Ranking Error**
- Actual taxonomy: **Comparison Ranking Error**
- Image assessment: **Partially correct** - The stated numeric data are rendered correctly, but a false trend/rank sentence does not alter the chart, so the visual alone does not expose that semantic error.
- Image: [generated_images/pie_comparison_ranking_error_3.png](generated_images/pie_comparison_ranking_error_3.png)

Essay:

The pie chart breaks down average Canadian household expenditure in 2024 across six spending categories.

Overall, Transport was the largest component of household expenditure, while the remaining categories occupied unequal shares.

Food represented 21% of the budget. Households devoted 17% of expenditure to Transport. Utilities represented 10% of the budget. Households devoted 32% of expenditure to Housing. Households devoted 12% of expenditure to Leisure. Households devoted 8% of expenditure to Other.

This distribution makes it possible to compare major commitments with smaller items of expenditure.

#### pie_key_feature_omission_1 - PASS

- Expected taxonomy: **Key Feature Omission**
- Actual taxonomy: **Key Feature Omission**
- Image assessment: **Correct** - The rendered chart matches the values and omissions stated in the essay.
- Image: [generated_images/pie_key_feature_omission_1.png](generated_images/pie_key_feature_omission_1.png)

Essay:

The pie chart breaks down average Canadian household expenditure in 2024 across six spending categories.

Overall, a few categories accounted for substantial portions of the budget, while the remaining shares were more limited.

The share allocated to Housing was 32%. The share allocated to Leisure was 12%. Households devoted 10% of expenditure to Utilities. Transport represented 17% of the budget. Other represented 8% of the budget.

Together, the listed components account for the complete household budget shown in the chart.

#### pie_key_feature_omission_2 - FAIL

- Expected taxonomy: **Key Feature Omission**
- Actual taxonomy: **None**
- Image assessment: **Incorrect** - Other/: expected None, rendered 8.0
- Image: [generated_images/pie_key_feature_omission_2.png](generated_images/pie_key_feature_omission_2.png)
- Failure analysis: The model copied the omitted category's official percentage into the student record even though the essay did not state it, so omission detection and the student-generated pie both failed.

Essay:

The circular chart presents the percentage distribution of Canadian household expenditure among six categories in 2024.

Overall, the household budget was divided into clearly unequal shares rather than being distributed evenly.

Households devoted 17% of expenditure to Transport. The share allocated to Utilities was 10%. Households devoted 21% of expenditure to Food. The share allocated to Leisure was 12%. The share allocated to Housing was 32%.

Together, the listed components account for the complete household budget shown in the chart.

#### pie_key_feature_omission_3 - FAIL

- Expected taxonomy: **Key Feature Omission**
- Actual taxonomy: **None**
- Image assessment: **Incorrect** - Leisure/: expected None, rendered 12.0
- Image: [generated_images/pie_key_feature_omission_3.png](generated_images/pie_key_feature_omission_3.png)
- Failure analysis: The model copied the omitted category's official percentage into the student record even though the essay did not state it, so omission detection and the student-generated pie both failed.

Essay:

The chart shows how an average household in Canada allocated its spending in 2024.

Overall, a few categories accounted for substantial portions of the budget, while the remaining shares were more limited.

Households devoted 17% of expenditure to Transport. The share allocated to Other was 8%. The share allocated to Utilities was 10%. Households devoted 21% of expenditure to Food. Housing represented 32% of the budget.

Together, the listed components account for the complete household budget shown in the chart.

## Failure patterns

1. **Line endpoint paraphrases are brittle.** Explicit years were reliable, while 'at the beginning/end' frequently failed to attach values to 2010/2020. This caused false endpoint omissions, missing line points, and in one case a missed value error.
2. **Pie omission can be overwritten by model inference.** Two of three omission essays had the missing official slice copied into the student record, producing a false negative and an incorrect full pie.
3. **Trend and ranking errors are not encoded by numeric rendering.** When all stated values are correct, a false verbal trend/rank leaves the generated chart visually identical to the correct data. The taxonomy panel detects the sentence, but image comparison alone cannot reveal it.
4. **Bar performance was stable in this batch.** All 15 randomized bar cases produced the exact intended taxonomy class and data-faithful images.
