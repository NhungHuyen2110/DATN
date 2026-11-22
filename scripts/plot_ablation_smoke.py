"""Plot actual observed smoke latency; explicitly not a relevance/controlled-performance benchmark."""
import argparse
import json
import math
from pathlib import Path
import statistics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='New figure path without extension')
    args = parser.parse_args()
    outputs = [args.output.with_suffix(suffix) for suffix in ('.png', '.svg', '.json')]
    if any(path.exists() for path in outputs):
        parser.error('Figure output already exists')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    summary = json.loads((args.results / 'summary.json').read_text(encoding='utf-8'))
    labels = {'lexical': 'Lexical token overlap', 'dense': 'Dense', 'dense_lexical': 'Dense + lexical',
              'dense_graph': 'Dense + graph', 'full_graph_reranked': 'Dense + lexical + graph\n+ experimental graph features'}
    stats = []
    for mode in summary['modes']:
        values = sorted(json.loads(line)['latency_seconds'] for line in
                        (args.results / (mode + '.predictions.jsonl')).read_text(encoding='utf-8').splitlines())
        stats.append({'mode': mode, 'n': len(values), 'median': statistics.median(values),
                      'p05': values[math.ceil(.05 * len(values)) - 1], 'p95': values[math.ceil(.95 * len(values)) - 1]})
    figure, ax = plt.subplots(figsize=(11, 6))
    median = [item['median'] * 1000 for item in stats]
    error = [[(item['median'] - item['p05']) * 1000 for item in stats],
             [(item['p95'] - item['median']) * 1000 for item in stats]]
    bars = ax.barh(range(len(stats)), median, xerr=error, color='#ae8a55', capsize=3, ecolor='#343b43')
    ax.set_yticks(range(len(stats)), [labels[item['mode']] for item in stats])
    ax.invert_yaxis()
    ax.set_xlabel('Measured query time (milliseconds)')
    ax.set_title('Observed latency across 105 draft queries — SMOKE ONLY', loc='left', fontweight='bold', pad=16)
    ax.spines[['top', 'right']].set_visible(False)
    ax.grid(axis='x', alpha=.2)
    ax.set_axisbelow(True)
    figure.text(.02, .02, 'Bars: median; whiskers: p05–p95 across queries (includes abstentions).\n'
                'Cached MiniLM CPU, Qdrant memory, test Neo4j, CSV seed. Fixed mode order and workstation load;\n'
                'not a controlled latency comparison, and not a relevance-quality benchmark.', fontsize=9, color='#4b5563')
    figure.tight_layout(rect=(0, .13, 1, 1))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(outputs[0], dpi=180)
    figure.savefig(outputs[1])
    plt.close(figure)
    with outputs[2].open('x', encoding='utf-8') as handle:
        json.dump({'source': str(args.results), 'measured_latency_only': True, 'quality_metrics': False, 'modes': stats}, handle, indent=2)
    print(json.dumps({'figure': str(outputs[0]), 'matplotlib': matplotlib.__version__, 'quality_claim': False}))


if __name__ == '__main__':
    main()
