from harbor import BaseEnvironment


class FileSystemToolHandler:
    def __init__(self, base_env: BaseEnvironment) -> None:
        self.env = base_env

    @staticmethod
    def _clean_bash_output(output: str | None) -> str:
        """Remove bash TTY warnings from output."""
        if not output:
            return ""

        lines = output.split('\n')
        cleaned_lines = [
            line for line in lines
            if not line.startswith('bash: cannot set terminal process group')
            and not line.startswith('bash: no job control in this shell')
        ]
        return '\n'.join(cleaned_lines)

    async def read_file(self, file_path: str) -> str:
        """Read a file from the environment."""
        try:
            result = await self.env.exec(f"cat {file_path}")
            if result.return_code != 0:
                return f"Error reading file {file_path}: {result.stderr or 'File not found'}"
            return self._clean_bash_output(result.stdout)
        except Exception as e:
            return f"Error reading file {file_path}: {str(e)}"

    async def edit_file(
        self, file_path: str, old_content: str, new_content: str
    ) -> str:
        """Edit a file in the environment using Python replacement."""
        try:
            # Use hex encoding for safe handling of special characters
            old_encoded = old_content.encode('utf-8').hex()
            new_encoded = new_content.encode('utf-8').hex()

            python_cmd = f"""python3 -c "
import sys
try:
    with open('{file_path}', 'r') as f:
        content = f.read()
except FileNotFoundError:
    print('Error: File does not exist', file=sys.stderr)
    sys.exit(2)
except Exception as e:
    print(f'Error reading file: {{e}}', file=sys.stderr)
    sys.exit(3)

old_str = bytes.fromhex('{old_encoded}').decode('utf-8')
new_str = bytes.fromhex('{new_encoded}').decode('utf-8')

if old_str not in content:
    print('Error: old_content not found', file=sys.stderr)
    sys.exit(1)

content = content.replace(old_str, new_str, 1)

try:
    with open('{file_path}', 'w') as f:
        f.write(content)
except Exception as e:
    print(f'Error writing file: {{e}}', file=sys.stderr)
    sys.exit(4)
"
"""

            result = await self.env.exec(python_cmd)

            if result.return_code == 2:
                return f"Error: File {file_path} does not exist"
            elif result.return_code == 1:
                return f"Error: The specified old_content was not found in {file_path}"
            elif result.return_code != 0:
                stderr = self._clean_bash_output(result.stderr)
                return f"Error editing file {file_path}: {stderr or 'Unknown error'}"

            return f"Successfully edited {file_path}"
        except Exception as e:
            return f"Error editing file {file_path}: {str(e)}"

    async def write_file(self, file_path: str, content: str) -> str:
        """Write content to a new file in the environment."""
        try:
            content_encoded = content.encode('utf-8').hex()

            python_cmd = f"""python3 -c "
import sys
import os

content = bytes.fromhex('{content_encoded}').decode('utf-8')

# Create parent directories if they don't exist
dir_path = os.path.dirname('{file_path}')
if dir_path:
    os.makedirs(dir_path, exist_ok=True)

try:
    with open('{file_path}', 'w') as f:
        f.write(content)
except Exception as e:
    print(f'Error writing file: {{e}}', file=sys.stderr)
    sys.exit(1)
"
"""

            result = await self.env.exec(python_cmd)

            if result.return_code != 0:
                stderr = self._clean_bash_output(result.stderr)
                return f"Error writing file {file_path}: {stderr or 'Unknown error'}"

            return f"Successfully wrote {file_path}"
        except Exception as e:
            return f"Error writing file {file_path}: {str(e)}"
