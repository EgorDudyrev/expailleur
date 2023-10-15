import re
import string
from functools import reduce

import caspailleur as csp


def read_data():
    with open('README.md') as file:
        text = file.read()
    text = re.findall('# Published Case Studies(.*)# ', text, re.DOTALL)[0].strip()
    examples_txt = text.split('##')[2:]

    data = dict(
        titles=[ex.split('\n')[0].strip() for ex in examples_txt],
        links=[re.findall(r'\*\*The link\*\*: (.*)', ex)[0] for ex in examples_txt],
        tags=[re.findall(r'\*\*Tags\*\*: (.*)\.', ex)[0].replace('`', '').split(', ') for ex in examples_txt],
        examples=examples_txt
    )

    all_tags = reduce(lambda a, b: set(a) | set(b), data['tags'])
    all_tags = sorted(all_tags, key=lambda tag: (len(tag), tag))
    tags_indices = [[all_tags.index(tag) for tag in tags] for tags in data['tags']]
    data['all_tags'] = all_tags
    data['tags_indices'] = tags_indices
    data['full_text'] = text
    return data


def compute_lattice(tags_indices: list[list[int]]):
    n_tags = max(max(indices) for indices in tags_indices)+1
    itemsets_ba = list(csp.base_functions.isets2bas(tags_indices, n_tags))
    attr_extents_ba = csp.np2bas(csp.bas2np(itemsets_ba).T)

    intents_ba = csp.list_intents_via_LCM(itemsets_ba)
    extents_ba = [
        reduce(lambda a, b: a & b, [attr_extents_ba[m] for m in intent.itersearch(True)])
        for intent in intents_ba
    ]
    ordering_child_ba = csp.sort_intents_inclusion(intents_ba)
    ordering_parent_ba = csp.inverse_order(ordering_child_ba)

    if not extents_ba[-1].any():
        intents_ba = intents_ba[:-1]
        extents_ba = extents_ba[:-1]
        ordering_child_ba = [children[:-1] for children in ordering_child_ba[:-1]]
        ordering_parent_ba = [parents[:-1] for parents in ordering_parent_ba[:-1]]

    intents_reduced_ba = [
        reduce(lambda a, b: a & (~b), [intents_ba[i] for i in parents.itersearch(True)], intent)
        for intent, parents in zip(intents_ba, ordering_parent_ba)
    ]
    extents_reduced_ba = [
        reduce(lambda a, b: a & (~b), [extents_ba[i] for i in children.itersearch(True)], extent)
        for extent, children in zip(extents_ba, ordering_child_ba)
    ]

    lattice_data = {}
    for bas_name in ['intents', 'intents_reduced', 'extents', 'extents_reduced', 'ordering_child', 'ordering_parent']:
        lattice_data[bas_name] = list(csp.base_functions.bas2isets(locals()[bas_name+'_ba']))
    return lattice_data


def form_mermaid_diagram(
        tags_isets: list[set[int]], all_tags: list[str],
        cases_isets: list[set[int]], case_titles: list[str], case_links: list[str],
        children_nodes: list[set[int]]
) -> str:
    nodes_symbols = list(string.ascii_uppercase)
    assert len(tags_isets) <= len(nodes_symbols), \
        f'Reduce the number of nodes to at most {len(nodes_symbols)} (given {len(tags_isets)})'

    nodes_lines = []
    for node_data in zip(nodes_symbols, tags_isets, cases_isets, children_nodes):
        symbol, tags_iset, cases_iset, children = node_data
        tags_verb = ',\\n'.join([all_tags[i] for i in tags_iset])
        cases_verb = ',\\n'.join([f"<a href='{case_links[i]}'>{case_titles[i]}</a>" for i in cases_iset])

        node_line = f"{symbol}[{tags_verb}\\n<b>{cases_verb}];"
        nodes_lines.append(node_line)

    edge_lines = [
        f"{nodes_symbols[node_i]} --> {nodes_symbols[child_i]};"
        for node_i, children in enumerate(children_nodes) for child_i in children
    ]

    mermaid_lines = ['```mermaid', 'graph TD;'] + nodes_lines + [''] + edge_lines + ['```']
    return '\n'.join(mermaid_lines)


def update_mermaid(mermaid_text):
    with open('README.md', 'r') as file:
        readme = file.read()

    old_mermaid = re.findall(r"```mermaid.*```", readme, re.DOTALL)[0]
    readme = readme.replace(old_mermaid, mermaid_text)

    with open('README.md', 'w') as file:
        file.write(readme)


if __name__ == '__main__':
    cases_data = read_data()
    lattice_data_indices = compute_lattice(cases_data['tags_indices'])
    mermaid = form_mermaid_diagram(
        lattice_data_indices['intents_reduced'], cases_data['all_tags'],
        lattice_data_indices['extents_reduced'], cases_data['titles'], cases_data['links'],
        lattice_data_indices['ordering_child']
    )
    update_mermaid(mermaid)
