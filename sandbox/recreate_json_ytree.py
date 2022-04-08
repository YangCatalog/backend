"""
This sandbox script go through all the files found in /var/yang/ytrees directory.
If size of the file is equal to 0, JSON tree is created using emit_tree plugin.
"""
import argparse
import glob
import os
from pathlib import Path

from pyang import plugin
from elasticsearchIndexing.pyang_plugin.json_tree import emit_tree
from utility.create_config import create_config
from utility.yangParser import create_context

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Process changed modules in a git repo')
    parser.add_argument('--time', type=str,
                        help='Modified time argument to find(1)', required=False)
    parser.add_argument('--config-path', type=str, default=os.environ['YANGCATALOG_CONFIG_PATH'],
                        help='Set path to config file')
    args = parser.parse_args()
    config_path = args.config_path
    config = create_config(config_path)
    save_file_dir = config.get('Directory-Section', 'save-file-dir')
    json_ytree = config.get('Directory-Section', 'json-ytree')

    jsons = glob.glob('{}/*.json'.format(json_ytree))
    num_of_jsons = len(jsons)
    i = 0
    for i, jsn in enumerate(jsons):
        print('tree {} {} out of {}'.format(jsn, i + 1, num_of_jsons))
        file_stat = Path(jsn).stat()
        if file_stat.st_size != 0:
            continue
        plugin.init([])
        ctx = create_context(save_file_dir)
        ctx.opts.lint_namespace_prefixes = []
        ctx.opts.lint_modulename_prefixes = []
        for p in plugin.plugins:
            p.setup_ctx(ctx)
        module = jsn.split('/')[-1]
        name_revision = module.split('@')
        name = name_revision[0]
        revision = name_revision[1].split('.')[0]
        all_modules_path = '{}/{}@{}.yang'.format(save_file_dir, name, revision)
        try:
            with open(all_modules_path, 'r') as f:
                parsed_module = ctx.add_module(all_modules_path, f.read())
        except Exception:
            print('Module not found {}'.format(all_modules_path))
        try:
            ctx.validate()
            if parsed_module is None:
                continue
        except Exception:
            print('Module {} can not be validated'.format(all_modules_path))

        with open('{}/{}@{}.json'.format(json_ytree, name, revision), 'w') as f:
            try:
                emit_tree([parsed_module], f, ctx)
            except Exception:
                # create empty file so we still have access to that
                f.write('')
