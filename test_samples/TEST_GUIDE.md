# Visual Feedback manual test pack

This pack contains the IELTS Academic Task 1 visual types enabled in VividWrite.
`Auto Detect` is a mode rather than a separate type.

## Support matrix

| Type | Original-image understanding | Sample Essay | Visual feedback |
| --- | --- | --- | --- |
| Bar | DePlot | DeepSeek | DeepSeek + Vega-Lite |
| Line | DePlot | DeepSeek | DeepSeek + Vega-Lite |
| Area | DePlot | DeepSeek | DeepSeek + Vega-Lite |
| Pie | DePlot with isolated-pie validation | DeepSeek | DeepSeek + Vega-Lite |
| Map | Qwen vision | Qwen vision | Wan reference-image editing |
| Process | Qwen vision | Qwen vision | Wan reference-image editing |

Map and process tasks do not use DePlot because a table cannot represent spatial
layout or arrow topology. Their Sample Essay button sends the uploaded image to
Qwen visual understanding directly.

## 1. Bar chart

Image: `charts/01_bar_recycling_rates.png`

Task:

> The bar chart below compares the percentage of households that recycled
> waste in five UK cities in 2015 and 2020. Summarise the information by
> selecting and reporting the main features, and make comparisons where
> relevant. Write at least 150 words.

Incomplete answer for visual-feedback testing:

> The bar chart compares household recycling in five British cities in 2015
> and 2020. Overall, recycling became more common in every city, and Bristol
> recorded the highest proportions in both years. Bristol rose from 42% to
> 55%, while Leeds increased from 35% to 48%. Manchester also experienced a
> substantial rise, reaching 46% in 2020. Sheffield stood at 38% initially and
> finished at just over half of households. Liverpool remained the weakest
> performer despite an improvement during the period.

## 2. Line graph

Image: `charts/02_line_daily_passengers.png`

Task:

> The line graph shows the average number of daily passengers using buses,
> rail services and the metro between 2010 and 2020. Summarise the information
> by selecting and reporting the main features, and make comparisons where
> relevant. Write at least 150 words.

Incomplete answer for visual-feedback testing:

> The graph illustrates daily public transport use from 2010 to 2020. Bus
> travel was initially the most popular mode at 1.8 million passengers, but it
> declined overall and ended at 1.3 million. In contrast, rail use doubled from
> 1.1 million to 2.2 million and became the leading mode by the end. Metro use
> also rose steadily, beginning at 0.8 million and reaching 1.9 million in
> 2020. Rail overtook buses around the middle of the period, while the metro
> finished between the other two services.

## 3. Area chart

Image: `charts/03_area_renewable_electricity.png`

Task:

> The area chart shows the amount of electricity generated from hydro, wind
> and solar power between 2000 and 2020. Summarise the information by selecting
> and reporting the main features, and make comparisons where relevant. Write
> at least 150 words.

Incomplete answer for visual-feedback testing:

> The chart compares electricity generation from three renewable sources over
> a twenty-year period. Overall, output from all sources increased, although
> wind and solar grew far more rapidly than hydro. Hydroelectric generation
> changed only moderately, rising from 45 TWh in 2000 to 55 TWh in 2020. Wind
> power climbed dramatically from just 5 TWh to 65 TWh and became the largest
> individual source at the end. Solar remained the smallest source, but its
> production also expanded considerably and reached 38 TWh in 2020.

## 4. Pie chart

Image: `charts/04_pie_household_spending.png`

Task:

> The pie chart shows how an average Canadian household distributed its
> expenditure among six categories in 2024. Summarise the information by
> selecting and reporting the main features, and make comparisons where
> relevant. Write at least 150 words.

Incomplete answer for visual-feedback testing:

> The chart presents average household spending in Canada in 2024. Housing was
> by far the largest expense, accounting for 32% of the total. Food ranked
> second at 21%, while transport represented 17%. Canadians allocated 12% of
> their spending to leisure and a further 10% to utilities. Overall, the three
> largest categories made up well over two thirds of household expenditure.

## 5. Map task

Image: `charts/06_map_riverside_town.png`

Task:

> The map shows the layout of Riverside town before redevelopment. Summarise
> the information by selecting and reporting the main features, and make
> comparisons where relevant. Write at least 150 words.

Use `Map Task`, upload the image and click `Sample Essay`. This checks that
Qwen reads the river, bridge, roads, school, market, forest, housing and compass
directions without requesting DePlot data.

Incomplete answer for visual-feedback testing:

> Riverside was divided by a river running from north to south, with an old
> bridge carrying the main road across the centre. A school stood in the
> north-west, while a market was located to the south-west. On the eastern side
> of the river, woodland occupied the north and housing lay in the south.

## 6. Process diagram

Image: `charts/07_process_glass_recycling.png`

Task:

> The diagram shows how used glass bottles are recycled. Summarise the
> information by selecting and reporting the main features, and make
> comparisons where relevant. Write at least 150 words.

Use `Process Diagram`, upload the image and click `Sample Essay`. The report
should identify a cyclical eight-stage process, beginning with disposal in
recycling bins and ending with delivery of new bottles to shops before the
cycle starts again.

Incomplete answer for visual-feedback testing:

> Used bottles are first deposited in recycling bins and collected by a truck.
> They are then sorted by colour and washed before being crushed into small
> pieces. The glass is subsequently melted in a furnace and moulded into new
> bottles, which are delivered to shops. After use, the bottles can be returned
> to the recycling system, making the process cyclical.

## Test procedure

1. Start the FastAPI backend and Vite frontend.
2. Open `http://localhost:5173` and sign in.
3. In Planning, choose the matching visual type and upload its PNG.
4. Click `Sample Essay` and confirm that an English report appears. Map and
   process requests may take longer because they call Qwen vision.
5. For visual feedback, replace the sample with the incomplete answer above.
6. Advance to Revision, click `Analyze Text`, then open `Visual Feedback`.
7. Confirm that the generated image follows the student's description and that
   missing or estimated information is not presented as an exact stated fact.
8. Repeat the pie test with `Auto Detect` after the explicit-type test passes.

## Pass criteria

- Sample Essay works for all six enabled types.
- Map and process Sample Essay calls do not request DePlot data.
- The process report preserves all eight stages and the correct arrow order.
- The page does not remain stuck on image analysis.
- Statistical feedback preserves category, series and colour order.
- Pie feedback marks incorrect values, shows a red missing wedge below 100%,
  and shows a red excess ring above 100%.
- Map/process visual feedback returns a Wan-generated image and displays its
  manual-review warning.
