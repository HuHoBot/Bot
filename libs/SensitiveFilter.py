import os
import glob


class SimpleSensitiveFilter:
    def __init__(self, dir_path="sensitive-words"):
        self.trie = {}
        # 加载所有敏感词
        for txt_file in glob.glob(os.path.join(dir_path, "*.txt")):
            with open(txt_file, "r", encoding="utf-8") as f:
                for line in f:
                    word = line.strip()
                    if word:
                        self._add_word(word)

    def _add_word(self, word):
        """构建字典树"""
        node = self.trie
        for char in word:
            if char not in node:
                node[char] = {}
            node = node[char]
        node["#"] = True  # 结束标记

    def replace(self, text, mask="*"):
        """直接替换敏感词"""
        result = list(text)
        n = len(text)
        i = 0

        while i < n:
            # 寻找最长匹配
            max_len = 0
            current_node = self.trie
            for j in range(i, n):
                char = text[j]
                if char in current_node:
                    current_node = current_node[char]
                    if "#" in current_node:
                        max_len = j - i + 1
                else:
                    break

            # 执行替换
            if max_len > 0:
                result[i:i + max_len] = [mask] * max_len
                i += max_len
            else:
                i += 1

        return "".join(result)