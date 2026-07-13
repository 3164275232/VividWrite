# Visual Feedback manual test pack

This pack covers every statistical chart type currently enabled in the
frontend. `Auto Detect` is a mode, not a separate chart type.

## Current support status

There are two different meanings of "supported" in the current prototype:

| Chart type | Unified DeepSeek/Vega-Lite pipeline | DePlot image extraction | End-to-end status |
| --- | --- | --- | --- |
| Bar | Supported | Near-exact in this test | Stable |
| Line | Supported | Near-exact in this test | Stable |
| Area | Supported | Series found, stacked values misread | Experimental |
| Pie | Supported | Labels and percentages misaligned | Experimental |
| Scatter | Supported | Axes and points misclassified | Experimental |

The distinction matters: Vega-Lite can render all five types, but the visual
feedback cannot be reliable when DePlot has already supplied an incorrect
official framework. The area, pie, and scatter fixtures are therefore included
both as feature tests and as reproducible known-limit tests.

Observed on the current backend:

- Bar: all cities and both years were extracted, with only small decimal
  approximations caused by reading bar heights.
- Line: all years and all three series were extracted correctly.
- Area: DePlot read stacked boundary heights instead of each source's value.
- Pie: DePlot produced a malformed repeated percentage table.
- Scatter: DePlot incorrectly invented a Year-based table and lost the x/y
  point structure.

## 1. Bar chart

Image: `charts/01_bar_recycling_rates.png`

Task:

> The bar chart below compares the percentage of households that recycled
> waste in five UK cities in 2015 and 2020. Summarise the information by
> selecting and reporting the main features, and make comparisons where
> relevant. Write at least 150 words.

Deliberately incomplete test answer:

> The bar chart compares household recycling in five British cities in 2015
> and 2020. Overall, recycling became more common in every city, and Bristol
> recorded the highest proportions in both years. Bristol rose from 42% to
> 55%, while Leeds increased from 35% to 48%. Manchester also experienced a
> substantial rise, reaching 46% in 2020. Sheffield stood at 38% initially and
> finished at just over half of households. Liverpool remained the weakest
> performer despite an improvement during the period.

Expected feedback: Liverpool's exact values and Sheffield's exact 2020 value
should be missing or uncertain; the other stated values should be retained.

## 2. Line chart

Image: `charts/02_line_daily_passengers.png`

Task:

> The line graph shows the average number of daily passengers using buses,
> rail services and the metro between 2010 and 2020. Summarise the information
> by selecting and reporting the main features, and make comparisons where
> relevant. Write at least 150 words.

Deliberately incomplete test answer:

> The graph illustrates daily public transport use from 2010 to 2020. Bus
> travel was initially the most popular mode at 1.8 million passengers, but it
> declined overall and ended at 1.3 million. In contrast, rail use doubled from
> 1.1 million to 2.2 million and became the leading mode by the end. Metro use
> also rose steadily, beginning at 0.8 million and reaching 1.9 million in
> 2020. Rail overtook buses around the middle of the period, while the metro
> finished between the other two services.

Expected feedback: endpoints should be present; intermediate values may be
estimated because the essay describes trends without listing every year.

## 3. Area chart

Image: `charts/03_area_renewable_electricity.png`

Task:

> The area chart shows the amount of electricity generated from hydro, wind
> and solar power between 2000 and 2020. Summarise the information by selecting
> and reporting the main features, and make comparisons where relevant. Write
> at least 150 words.

Deliberately incomplete test answer:

> The chart compares electricity generation from three renewable sources over
> a twenty-year period. Overall, output from all sources increased, although
> wind and solar grew far more rapidly than hydro. Hydroelectric generation
> changed only moderately, rising from 45 TWh in 2000 to 55 TWh in 2020. Wind
> power climbed dramatically from just 5 TWh to 65 TWh and became the largest
> individual source at the end. Solar remained the smallest source, but its
> production also expanded considerably and reached 38 TWh in 2020.

Expected feedback: beginning and ending values should appear; most intermediate
values should be estimated or missing.

## 4. Pie chart

Image: `charts/04_pie_household_spending.png`

Task:

> The pie chart shows how an average Canadian household distributed its
> expenditure among six categories in 2024. Summarise the information by
> selecting and reporting the main features, and make comparisons where
> relevant. Write at least 150 words.

Deliberately incomplete test answer:

> The chart presents average household spending in Canada in 2024. Housing was
> by far the largest expense, accounting for 32% of the total. Food ranked
> second at 21%, while transport represented 17%. Canadians allocated 12% of
> their spending to leisure and a further 10% to utilities. Overall, the three
> largest categories made up well over two thirds of household expenditure.

Expected feedback: the 8% Other slice should be missing, so the generated pie
should visibly differ from the original.

## 5. Scatter plot

Image: `charts/05_scatter_study_and_scores.png`

Task:

> The scatter plot compares weekly independent study time with average
> examination scores in eight countries from Europe and Asia. Summarise the
> information by selecting and reporting the main features, and make
> comparisons where relevant. Write at least 150 words.

Deliberately incomplete test answer:

> The scatter plot indicates a clear positive relationship between independent
> study and examination performance. Country A recorded the lowest figures,
> with four hours of study and an average score of 58. At the opposite end,
> country F studied for 11.5 hours and achieved 88. Countries spending roughly
> seven to ten hours on independent study generally scored between 70 and 85.
> The broad pattern was similar in Europe and Asia, although the two
> highest-scoring observations belonged to Asian countries.

Expected feedback: A and F should be exact; the middle observations may be
estimated or missing. The overall upward relationship should remain visible.

## Test procedure

1. Start the FastAPI backend and Vite frontend.
2. Open `http://localhost:5173` and sign in.
3. In Planning, choose the matching chart type. Avoid Auto Detect for the first
   pass so that data alignment and rendering are tested independently.
4. Upload the corresponding PNG from this pack.
5. Advance to Drafting and paste the supplied test answer.
6. Advance to Revision, then click `Analyze Text`.
7. Open `Visual Feedback` and compare the generated chart with the original.
8. Confirm that stated facts are shown, omitted facts are absent, and inferred
   facts are treated as estimates rather than copied from the original.
9. Repeat steps 3-8 for all five images.
10. Finally, repeat the pie test with `Auto Detect`. A clearly colored circular
    chart should be detected locally as a pie before DeepSeek alignment. Then
    repeat one bar or line test to confirm those images are not misclassified
    as pies.

For the first acceptance round, treat Bar and Line as pass/fail product tests.
Treat Area, Pie, and Scatter as diagnostic tests: inspect the DePlot result and
record the known extraction failure before judging the downstream chart.

## Pass criteria

- The page does not remain stuck on image analysis.
- The backend returns a `/charts/visual_feedback_*.png` URL.
- The generated PNG loads in Visual Feedback.
- Categories and series follow the original chart framework.
- Values come from the essay, not silently from the original chart.
- Missing and estimated information is visibly different from exact facts.
- No old `bar.py` or `pie.py` path is required for generation.
