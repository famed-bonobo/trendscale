"""Seven AI assistants on one Google Trends scale, which Google's own page cannot show (it stops at five terms).

python examples/ai_assistants.py
"""

from statistics import mean

from trendscale import Trends

ASSISTANTS = ['chatgpt', 'gemini', 'claude', 'perplexity', 'copilot', 'deepseek', 'grok']

with Trends() as trends:
    timelines = trends.interest_over_time(ASSISTANTS, geo='US', time_range='past_12_months')

for term, timeline in sorted(timelines.items(), key=lambda item: -mean(point['value'] for point in item[1][-4:])):
    recent = mean(point['value'] for point in timeline[-4:])
    year_ago = mean(point['value'] for point in timeline[:4])
    print(f'{term:<11} last 4 weeks {recent:5.1f}   a year ago {year_ago:5.1f}')
