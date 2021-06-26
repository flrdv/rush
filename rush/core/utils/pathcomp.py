import re

"""
TODO: use it by default for routing paths
"""

tag_form = re.compile(r'<\S*>')


def compare_paths(template, path):
    kwargs = {}
    template_elements, path_elements = template.split('/'), path.split('/')

    if len(template_elements) != len(path_elements):
        return None

    for template_element, path_element in zip(template_elements, path_elements):
        if tag_form.fullmatch(template_element):
            kwargs[template_element[1:-1]] = path_element
        elif template_element != path_element:
            return None  # usual element, but doesn't matches

    return kwargs
