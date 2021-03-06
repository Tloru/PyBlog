from . import *

import os

import flask

from mistune import markdown as md
from m2r import convert as rst

from fuzzywuzzy import fuzz as f
import unicodedata

def simplify(string): return unicodedata.normalize('NFKD', string).encode('ascii', 'ignore').lower()

def find_difference(base_path, addition):
    common = os.path.commonpath([base_path, addition])
    relative = addition[len(common):]
    return "/" if relative == "" else relative

# TODO: fix the .veritableignore code in list_folders/files

def list_folders(vignore, path):
    # get all folders
    folders = [x for x in os.listdir(path) if os.path.isdir(join(path, x))]
    # folders = list(filter(lambda x: False if vignore(join(path, x)) else True, folders))
    folders = list(filter(lambda x: False if x == "src" or x[0] == "." else True, folders))
    return folders

def list_files(vignore, path):
    # get all folders
    # remove hidden files
    files = [x for x in os.listdir(path) if os.path.isfile(join(path, x))]
    # files = list(filter(lambda x: False if vignore(join(path, x)) else True, files))
    files = list(filter(lambda x: False if x[0] == "." else True, files))
    return files

def fuzz(vignore, path, addition, child_rule=(lambda path: os.listdir(path)), min_sim=90):
    """
    path: a path-like object
    addition: a folder or file name
    child_rule: function that lists the name of all children given a path
    min_sim: minimum similarity of paths
    returns:
    """
    # find all children in directory and filter out some children.
    # get the score for each child
    # find the best score
    # find the child with the closest name
    # make sure child name isn't too different from desired name
    children = child_rule(vignore, path)

    scores = [f.ratio(simplify(addition), simplify(child)) for child in children]
    best = max(scores)
    best_child = children[scores.index(best)]
    print(best, best_child, addition)
    assert best >= min_sim

    # return the full path to the child
    return join(path, best_child)

list_all = lambda vignore, x: list_folders(vignore, x) + list_folders(vignore, x)

def fuzz_path(vignore, path, additions):
    # handle corner cases
    if len(additions) == 0: return path
    if len(additions) == 1:
        return fuzz(
            vignore,
            path,
            additions[0],
            child_rule=list_all,
            min_sim=0)

    folders, file = additions[:-1], additions[-1]

    for folder in folders:
        path = join(path, fuzz(
        vignore,
            path,
            folder,
            child_rule=list_folders,
            min_sim=90))

    path = join(path, fuzz(
        vignore,
        path,
        file,
        child_rule=list_all,
        min_sim=0))

    return path

def render_folder(env, sections, path, full_path):
    files = list_files(env.vignore, full_path)
    folders = list_folders(env.vignore, full_path)
    all = files + folders

    index = list(filter(lambda x: os.path.splitext(x)[0] == "index", files))

    if len(index) != 1: index = None
    else: index = index[0]

    if len(files) == 1 and len(folders) == 0 or index is not None:
        file = index if index is not None else files[0]
        return render_file(env, sections, join(full_path, file))

    relatives = list(map(lambda x: find_difference(path, join(full_path, x)), all))
    all = list(zip(relatives, all))

    return flask.render_template(
        "section.html",
        pages=all,
        section=os.path.basename(full_path),
        sections=sections,
        name=env.name,
        author=env.author,
        description=env.description,
    )

def render_file(env, sections, full_path):
    markup = {
        ".md": md,
        ".rst": rst
    }

    file, ext = os.path.splitext(full_path)
    with open(full_path, "r") as f:
        data = f.read()

    if ext in markup:
        page = flask.Markup(markup[ext](data))
    else:
        page = flask.Markup("<pre>\n<code>{}\n</code></pre>".format(flask.escape(data)))

    return flask.render_template(
        "page.html",
        page=page,
        sections=sections,
        name=env.name,
        author=env.author,
        description=env.description,
    )

def parse(path_list, env):
    if path_list[0] == "": path_list = []
    path = env.project_path

    full_path = fuzz_path(env.vignore, path, path_list)
    base_path = os.path.split(full_path)[0]

    sections = list_folders(env.vignore, base_path)
    relatives = list(map(lambda x: find_difference(path, join(base_path, x)), sections))
    sections = list(zip(relatives, sections))

    if path_list != [""]: sections = [(find_difference(path, base_path), "← Back")] + sections

    if os.path.isdir(full_path): template = render_folder(env, sections, path, full_path)
    else: template = render_file(env, sections, full_path)

    return template
