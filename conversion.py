import json
import os
import sys
import glob
import re
from datetime import datetime


def read_json_file(file_path):
    """Read and return JSON content from a file."""
    with open(file_path, 'r', encoding='utf-8') as file:
        return json.load(file)


def get_message_content(message):
    """Return a list of content parts from a message: either strings or image dicts."""
    content = message.get("content", {})
    parts = []

    if "parts" in content:
        for part in content["parts"]:
            if isinstance(part, dict):
                parts.append(part)  # image or other structured content
            else:
                parts.append({"text": str(part)})
    elif "text" in content:
        parts.append({"text": content["text"]})
    elif "result" in content:
        parts.append({"text": content["result"]})
    else:
        raise ValueError(f"Unknown message format: {content}")
    return parts



def infer_title(title, first_message):
    """Return the given title or infer it from the first message content."""
    if title:
        return title

    parts = get_message_content(first_message)
    for part in parts:
        if "text" in part:
            first_line = part["text"].strip().split("\n", 1)[0]
            return first_line + "..."

    return "Untitled"



def get_backtick_wrapper(content):
    """Return a safe backtick sequence to wrap code blocks containing backticks."""
    backticks = re.findall(r'`+', content)
    max_len = max((len(b) for b in backticks), default=2)
    return '`' * (max_len + 1)


def sanitize_filename(name):
    """Remove illegal characters from a filename."""
    return ''.join(c for c in name if c.isalnum() or c in (' ', '_')).rstrip().replace(' ', '_')

def convert_latex(content):
    """Convert LaTeX delimiters: \( \) → $ $, \[ \] → $$ $$"""
    content = re.sub(r'\\\((.+?)\\\)', r'$\1$', content, flags=re.DOTALL)
    content = re.sub(r'\\\[(.+?)\\\]', r'$$\1$$', content, flags=re.DOTALL)
    return content


def process_conversations(data, output_dir, config):
    """Convert a list of conversation entries into formatted markdown files."""
    for entry in data:
        if not isinstance(entry, dict):
            print(f"Skipping entry (not a dict): {entry}")
            continue

        
        mapping = entry.get("mapping", {})
        messages = [
            item["message"] for item in mapping.values()
            if isinstance(item, dict) and isinstance(item.get("message"), dict)
        ]

        messages.sort(key=lambda m: m.get("create_time") or float('-inf'))

        if not messages:
            print("Skipping conversation with no messages.")
            continue
        
        inferred_title = infer_title(entry.get("title"), messages[0])
        sanitized_title = sanitize_filename(inferred_title)

        first_timestamped = next((m for m in messages if m.get("create_time")), None)

        # Optional date prefix
        if config.get("prefix_date_in_filename") and first_timestamped:
            date_prefix = datetime.fromtimestamp(first_timestamped["create_time"]).strftime("%Y-%m-%d")
            filename = f"{date_prefix}_{sanitized_title}"
        else:
            filename = sanitized_title

        file_path = os.path.join(output_dir, f"{filename}.md")

        with open(file_path, "w", encoding="utf-8") as f:
            first_timestamped = next((m for m in messages if m.get("create_time")), None)                
                
            if config.get("obsidian_front_matter", False):
                f.write("---\n")
                f.write(f"title: {inferred_title}\n")
                if first_timestamped:
                    date_str = datetime.fromtimestamp(first_timestamped["create_time"]).strftime(config["date_format"])
                    f.write(f"date: {date_str}\n")
                f.write("---\n\n")
                

            image_counter = 1  # Keep track of image number per file

            for message in messages:
                role = message.get("author", {}).get("role", "unknown")
                content_parts = get_message_content(message)
                content = ""
                
                if config.get("include_timestamps") and message.get("create_time"):
                    timestamp = datetime.fromtimestamp(message["create_time"]).strftime(config["time_format"])
                    f.write(f"<sub>{timestamp}</sub>\n")

                for part in content_parts:
                    # If it's an image
                    if part.get("content_type") == "image_asset_pointer":
                        asset_pointer = part.get("asset_pointer", "")
                        file_id = None

                        # Match file-service://file-XYZ
                        if asset_pointer.startswith("file-service://"):
                            match = re.search(r'file-service://(file-[a-zA-Z0-9]+)', asset_pointer)
                            if match:
                                file_id = match.group(1)

                        # Match sediment://file_ABC
                        elif asset_pointer.startswith("sediment://"):
                            match = re.search(r'sediment://(file_[a-f0-9]+)', asset_pointer)
                            if match:
                                file_id = match.group(1)
                        if match:                           
                            # Default to normal input_directory
                            input_folder = config["input_directory"]
                            
                            # Special handling for dalle-generated images
                            if message.get("author", {}).get("role") == "tool" and message.get("author", {}).get("name") == "dalle.text2im":
                                input_folder = os.path.join(input_folder, "dalle-generations")

                            image_files = [f for f in os.listdir(input_folder) if f.startswith(file_id)]

                            if image_files:
                                original_image_path = os.path.join(input_folder, image_files[0])
                                image_ext = os.path.splitext(image_files[0])[1]
                                new_image_filename = f"{filename}_image_{image_counter}{image_ext}"
                                new_image_path = os.path.join(output_dir, new_image_filename)

                                # Copy image file
                                with open(original_image_path, 'rb') as src, open(new_image_path, 'wb') as dst:
                                    dst.write(src.read())

                                # Optional: include prompt if dalle metadata is present
                                metadata = part.get("metadata")
                                dalle_prompt = ""
                                if isinstance(metadata, dict):
                                    dalle_info = metadata.get("dalle")
                                    if isinstance(dalle_info, dict):
                                        dalle_prompt = dalle_info.get("prompt", "")

                                if dalle_prompt:
                                    f.write(f"**{author} (DALL·E)**: *{dalle_prompt}*\n")

                                image_code = f'\n<img src="{new_image_filename}" alt="Generated image" width="400">\n\n'
                                f.write(f"{image_code}")
                                image_counter += 1
                            else:
                                print(f"Image file not found for file_id: {file_id}")


                    else:
                        text = part.get("text", "")
                        content += text + "\n"


                if config.get("skip_empty_messages") and not content:
                    continue

                author = config["user_name"] if role == "user" else config["LLM_name"]

                


                use_code_block = role == "user" or '```' in content
                if config.get("convert_latex_syntax"):
                    content = convert_latex(content)

                num_lines = len(content.splitlines())
                collapse = config.get("collapse_long_messages") and num_lines > config.get("long_message_line_threshold", 5)

                if collapse:
                    open_attr = " open" if config.get("collapse_open_by_default") else ""
                    f.write(f"**{author}**:\n\n<details{open_attr}><summary>Long Message with {num_lines} lines</summary>\n\n")

                if use_code_block:
                    wrapper = get_backtick_wrapper(content)
                    f.write(f"{wrapper}\n{content}\n{wrapper}")
                else:
                    f.write(f"{content}")

                if collapse:
                    f.write("\n\n</details>")

                f.write(config['message_separator'])

                if collapse:
                    f.write("\n\n")



def main():
    config_path = "config.json"
    config = read_json_file(config_path)

    conversations_file = config.get("input_directory") + "/conversations.json"
    output_dir = config.get("output_directory")

    os.makedirs(output_dir, exist_ok=True)

    json_file = conversations_file
    print(f"Processing: {json_file}")
    data = read_json_file(json_file)
    process_conversations(data, output_dir, config)

    print(f"\n✅ All Done! Your files are ready in: {output_dir}")


if __name__ == "__main__":
    main()
