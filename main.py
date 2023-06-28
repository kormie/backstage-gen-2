from github import Github
from git import Repo
import yaml
from yaml import Dumper
from yaml.emitter import Emitter, ScalarAnalysis
import shutil
import textwrap
import re

TOKEN = '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'

class CustomDumper(Dumper):
    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)

def represent_list(self, data):
    node = super(Emitter, self).represent_sequence(u'tag:yaml.org,2002:seq', data, flow_style=False)
    return node

CustomDumper.add_representer(list, represent_list)

def get_repo(repo_url):
    g = Github(TOKEN)
    repo_path = repo_url.split('github.com/')[-1]
    return g.get_repo(repo_path)

def check_for_swagger(contents):
    for content_file in contents:
        if content_file.path == 'swagger':
            return True
    return False

def generate_catalog_info_yaml(repo_url, system, owner):
    repo = get_repo(repo_url)
    repo_name = repo.name
    repo_title_name = repo_name.replace('-', ' ').title()
    contents = repo.get_contents("")
    swagger_exists = check_for_swagger(contents)

    data = {
        'apiVersion': 'backstage.io/v1alpha1',
        'kind': 'Component',
        'metadata': {
            'name': f'{repo_name}-service',
            'description': f'{repo_title_name} Service',
            'tags': ['go', 'eevee', 'rest'],
            'annotations': {
                'yamllint_comment': 'placeholder',
                'backstage.io/techdocs-ref': f'url:{repo.html_url}/blob/development/',
                'github.com/project-slug': repo.full_name
            },
        },
        'spec': {
            'type': 'service',
            'owner': owner,
            'lifecycle': 'production',
            'providesApis': [f'{repo_name}-api'],
            'system': system,
        }
    }

    yaml_str = yaml.dump(data, Dumper=CustomDumper, default_flow_style=False, sort_keys=False)

    if swagger_exists:
        swagger_data = {
            'apiVersion': 'backstage.io/v1alpha1',
            'kind': 'API',
            'metadata': {
                'name': f'{repo_name}-api',
                'description': f'{repo_title_name} API',
                'tags': ['rest'],
            },
            'spec': {
                'type': 'openapi',
                'lifecycle': 'production',
                'owner': owner,
                'apiProvidedBy': repo_name,
                'definition': {
                    'yamllint_comment': 'placeholder',
                    '$text': f'{repo.html_url}/blob/development/swagger/swagger.yaml'
                }
            }
        }
        yaml_str += '\n---\n'
        yaml_str += yaml.dump(swagger_data, Dumper=CustomDumper, default_flow_style=False, sort_keys=False)

    yaml_str = yaml_str.replace('yamllint_comment: placeholder\n', '# yamllint disable-line rule:line-length\n')

    with open('catalog-info.yaml', 'w') as outfile:
        outfile.write(yaml_str)

def get_markdown_files(repo, path=''):
    markdown_files = []
    contents = repo.get_contents(path)
    for content_file in contents:
        if content_file.path.lower().endswith('readme.md'):
            if content_file.path.lower() == 'readme.md':
                title = 'Home'
            else:
                # Remove 'readme.md' from the path and split the remaining path into segments
                segments = content_file.path.lower().replace('readme.md', '').split('/')
                # Remove empty segments and title case the remaining segments
                segments = [segment.replace('_', ' ').title() for segment in segments if segment]
                title = ' - '.join(segments)
            markdown_files.append({title: content_file.path})
        elif content_file.type == 'dir':
            markdown_files.extend(get_markdown_files(repo, content_file.path))
    return markdown_files

def generate_mkdocs_yaml(repo_url):
    repo = get_repo(repo_url)
    repo_name = repo.name
    repo_title_name = repo_name.replace('-', ' ').title()
    markdown_files = get_markdown_files(repo)

    data = {
        'site_name': f'{repo_title_name} Service',
        'plugins': ['techdocs-core'],
        'nav': markdown_files,
        'markdown_extensions': [
            {'pymdownx.snippets': {'check_paths': True}}
        ]
    }

    with open('mkdocs.yaml', 'w') as outfile:
        yaml.dump(data, outfile, Dumper=CustomDumper, default_flow_style=False, sort_keys=False)

def get_https_url_from_ssh(url):
    if "git@" not in url:
        return url
    url = url.replace("git@", "https://").replace(".com:", ".com/").replace(".git", "")
    return url

def format_text(text):
    # Replace "`word~`" with "\033[1mword\033[0m" for bold formatting
    return re.sub(r'`([^`]+)~`', r'\033[1m\1\033[0m', text)

def get_visible_length(line):
    # Calculate the visible length of a line by removing ANSI escape sequences
    escape_seq_pattern = r'\033\[\d+m'
    visible_line = re.sub(escape_seq_pattern, '', line)
    return len(visible_line)

def print_welcome_message():
    terminal_width = shutil.get_terminal_size().columns
    padding = 10
    welcome_message = """
    This script will generate the `catalog-info.yaml~` and `mkdocs.yaml~` files for a KOHO service. If the current directory is a Git repository, the script will use the repo's `remote/origin~` URL to generate the files. Otherwise, you'll be prompted for the URL.

    
    If you're not sure what to enter for the `SYSTEM~` and `OWNER~`, you can find them here: `https://github.com/kohofinancial/documentation/tree/main/architecture/domains~`.
    """

    # Preserve the newlines in the original heredoc
    welcome_message = welcome_message.strip()

    # Apply formatting to words surrounded by "`" and "~`" marks
    welcome_message = format_text(welcome_message)

    # Calculate the remaining available space in the terminal
    available_space = terminal_width - (padding * 2 + 2)  # 2 for the "#" symbols

    # Split the welcome message into lines
    message_lines = welcome_message.splitlines()

    # Wrap each line of the welcome message to fit within the available space
    wrapped_lines = []
    for line in message_lines:
        wrapped_lines.extend(textwrap.wrap(line, width=available_space))

    print()
    # Print the padded welcome message surrounded by "#" symbols
    print("#" * terminal_width)
    print("#" + " " * (padding) + " " * available_space + " " * padding + "#")

    for line in wrapped_lines:
        line_padding = padding + (available_space - get_visible_length(line))
        print("#" + " " * padding + line + " " * line_padding + "#")

    print("#" + " " * (padding) + " " * available_space + " " * padding + "#")
    print("#" * terminal_width)
    print()

def main():
    print_welcome_message()
    try:
        repo = Repo('.')
        repo_url = next(repo.remote('origin').urls)
        repo_url = get_https_url_from_ssh(repo_url)
        text = f'`Using repo URL~`: {repo_url}'
        text = format_text(text)
        print(text)
    except Exception:
        # If the current directory is not a Git repository, prompt the user for the URL
        repo_url = input(format_text("`Enter the GitHub repo URL~`: "))
    system = input(format_text('`Enter the system name~`: '))
    owner = input(format_text('`Enter the owner name~`: '))

    generate_catalog_info_yaml(repo_url, system, owner)
    generate_mkdocs_yaml(repo_url)

if __name__ == "__main__":
    main()
