import argparse
import glob
import os
from utility.create_config import create_config
from pyang import plugin
from pyang.plugins.json_tree import emit_tree
from scripts.yangParser import create_context
from pathlib import Path

if __name__ == '__main__':
    #find_args = []

    parser = argparse.ArgumentParser(
        description="Process changed modules in a git repo")
    parser.add_argument('--time', type=str,
                        help='Modified time argument to find(1)', required=False)
    parser.add_argument('--config-path', type=str, default=os.environ['YANGCATALOG_CONFIG_PATH'],
                        help='Set path to config file')
    args = parser.parse_args()
    config_path = args.config_path
    config = create_config(config_path)
    save_file_dir = config.get('Directory-Section', 'save-file-dir')
    ytree_dir = config.get('Directory-Section', 'json-ytree')

    jsons = glob.glob("{}/*.json".format(ytree_dir))
    i = 0
    for jsn in jsons:
        i += 1
        print('tree {} {} out of {}'.format(jsn, i , len(jsons)))
        file_stat = Path('{}'.format(jsn)).stat()
        if file_stat.st_size != 0:
            continue
        plugin.init([])
        ctx = create_context('{}'.format(save_file_dir))
        ctx.opts.lint_namespace_prefixes = []
        ctx.opts.lint_modulename_prefixes = []
        for p in plugin.plugins:
            p.setup_ctx(ctx)
        module = jsn.split('/')[-1]
        name_revision = module.split('@')
        name = name_revision[0]
        revision = name_revision[1].split('.')[0]
        m = '{}/{}@{}.yang'.format(save_file_dir, name, revision)
        try:
            with open(m, 'r') as f:
                parsed_module = ctx.add_module(m, f.read())
        except:
            print('not found ' + m)
        try:
            ctx.validate()
            if parsed_module is None:
                continue
        except:
            print('module {} can not be validated'.format(m))

        with open('{}/{}@{}.json'.format(ytree_dir, name, revision), 'w') as f:
            try:
                emit_tree([parsed_module], f, ctx)
            except:
                # create empty file so we still have access to that
                f.write("")
