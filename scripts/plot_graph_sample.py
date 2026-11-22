"""Render only relationships exported from the isolated graph; never generates product facts."""
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / '.local-tmp/matplotlib'))


def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyArrowPatch
    source = ROOT / 'docs/figures/graph-sample-live.json'
    record = json.loads(source.read_text(encoding='utf-8'))
    if record.get('read_only') is not True or len(record['products']) != 2:
        raise ValueError('Expected the actual two-product read-only graph export')
    positions = {}
    names = {}
    for pid, y in zip(record['products'], (0.78, 0.22)):
        positions[('Product', pid)] = (0.12, y)
    attributes = []
    for edge in record['edges']:
        data, label = edge['attributes'], edge['label']
        ids = [(key, value) for key, value in data.items() if key.endswith('_id')]
        if len(ids) != 1:
            raise ValueError('Exactly one stable taxonomy ID required')
        key = (label, ids[0][1])
        if key not in attributes:
            attributes.append(key)
        names[key] = label + ' #' + str(key[1]) + '\n' + data['name']
        names[('Product', edge['product_id'])] = 'Product #' + str(edge['product_id']) + '\n' + edge['product_name']
    for index, key in enumerate(attributes):
        positions[key] = (0.76, 0.92 - index * 0.84 / max(1, len(attributes) - 1))
    fig, ax = plt.subplots(figsize=(14, 10))
    ax.set(xlim=(0, 1), ylim=(0, 1))
    ax.axis('off')
    colors = {record['products'][0]: '#2166ac', record['products'][1]: '#b35806'}
    for edge in record['edges']:
        target = (edge['label'], next(value for key, value in edge['attributes'].items() if key.endswith('_id')))
        start, end = positions[('Product', edge['product_id'])], positions[target]
        ax.add_patch(FancyArrowPatch(start, end, arrowstyle='-|>', mutation_scale=12,
                                    shrinkA=53, shrinkB=72, linewidth=1.4, alpha=.65,
                                    color=colors[edge['product_id']]))
        # Distinct points along each edge reduce overlapping labels near shared nodes.
        t = .38 if edge['product_id'] == record['products'][0] else .59
        x, y = start[0] * (1-t) + end[0] * t, start[1] * (1-t) + end[1] * t
        ax.text(x, y, edge['relationship'], fontsize=8, rotation=0, ha='center', va='center',
                color=colors[edge['product_id']], bbox={'facecolor': 'white', 'edgecolor': 'none', 'alpha': .85})
    for key, (x, y) in positions.items():
        ax.text(x, y, names[key], ha='center', va='center', fontsize=11,
                bbox={'boxstyle': 'round,pad=0.65', 'facecolor': '#e5f0fa' if key[0] == 'Product' else '#f1f4f6',
                      'edgecolor': '#526475', 'linewidth': 1.2})
    fig.suptitle('LUMIÈRE — actual Neo4j relationship sample', fontsize=17, y=.98)
    fig.text(.5, .025, 'Read-only export from isolated test graph • CSV seed projection • Not a Neo4j Browser screenshot',
             ha='center', fontsize=10, color='#444444')
    for suffix in ('png', 'svg'):
        fig.savefig(ROOT / ('docs/figures/graph-sample-live.' + suffix), dpi=160, bbox_inches='tight')
    plt.close(fig)
    metadata = {'source': source.name, 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                'nodes': len(positions), 'edges': len(record['edges']), 'manual_fact_creation': False,
                'scope': record['scope'], 'neo4j_browser_screenshot': False}
    (ROOT / 'docs/figures/graph-sample-render.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(metadata))


if __name__ == '__main__':
    main()
