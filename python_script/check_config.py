#!/bin/python3
# -*- coding:utf-8 -*-

'''
Brief:
This is a pre-commit git hook
Check whether config modifications are applied to all json configs.
'''



import subprocess
import traceback
import sys
import re
import os
import json
import copy
from enum import Enum

# regex expression for config name
CONFIG_PATTERN = r".*dummy_config.*\.json$"
# list of project's path
PROJ = ['proj_a', 'proj_b', 'proj_c']

class ChangeType(Enum):
    Add = 1,
    Delete = 2
    Update = 3

class ChangeOperation:
    def __init__(self, change_type:ChangeType, change_file:str, parameter=-1):
        self.change_type = change_type
        self.change_file = change_file
        self.parameter = parameter

    def __eq__(self, obj):
        if (self.change_type == obj.change_type and
            self.parameter == obj.parameter):
            return True

        return False

class ChangesForOnePath:
    def __init__(self, json_path:list):
        self.json_path = json_path
        self.change_list = [] # ChangeOperation的列表

    def append(self, change_operation:ChangeOperation):
        self.change_list.append(change_operation)

    def __getitem__(self, key):
        return self.change_list[key]

    def __hash__(self):
        return len(self.json_path)

    '''
    如果ChangesForOnePath的set通过add函数添加两个拥有相同json_path的ChangesForOnePath对象
    那么仅仅在原有的ChangesForOnePath的change_list中添加ChangeOperation，而不是set再添加一个ChangesForOnePath
    '''
    def __eq__(self, other):
        if self.json_path == other.json_path:
            for change_operation in other.change_list:
                self.change_list.append(change_operation)

        return self.json_path == other.json_path
    
    '''
    将self.change_list按山头分类

    @return {changed_file_for_proj} key为山头名字，value为该山头在json_path有改动的配置列表
    '''
    def classification(self):
        changed_file_for_proj = dict()

        for change in self.change_list:
            proj = change.change_file.split("/")[1]

            if proj not in changed_file_for_proj.keys():
                changed_file_for_proj[proj] = []

            changed_file_for_proj[proj].append(change)

        return changed_file_for_proj

'''
访问一个dict在path处的value

@return path处不存在value, return ('false')
        path处存在value, return ('true', value)
'''
def getDictValueFromPath(dic:dict, path:list) -> tuple:
    ret = dic
    for i in range(len(path)):
        if isinstance(ret, dict):
            if path[i] not in ret.keys():
                return ("false")
            ret = ret[path[i]]
        else:
            raise Exception(f"try to get value from a wrong path, dict is {dic},path is {path}")
    return ("true", ret)


def printNotChangedOperation(config_file_name:str, json_path:list):
    with open(config_file_name, 'r', encoding='utf-8') as file:
        try:
            json_obj = json.load(file)
        except Exception as e:
            print(f"\033[31m {config_file_name} JSON解析失败,请检查是否为合法的json格式\033[0m")
            return

    val = getDictValueFromPath(json_obj, json_path)

    printHighlightFileName(config_file_name)
    if val == "false":
        print(f" 下没有该值, \033[31m且本次commit未添加\033[0m")
    elif val[0] == "true":
        print(f" 下该值为 \033[32m{val[1]}\033[0m, \033[31m本次commit未改动\033[0m")

    file.close()


def printHighlightFileName(config_file_name):
    split = config_file_name.split('/')

    s = "  " + split[0]
    for index in range(1, len(split)):
        s += "/"
        if index == 1 or index == len(split) - 1:
            s += f"\033[32m{split[index]}\033[0m"
        else:
            s += split[index]
    formatted_s = '{:>91}'.format(s)
    print(formatted_s, end="")

def printChangedOperation(printing:ChangeOperation):
    printHighlightFileName(printing.change_file)
    print(f" 文件对其进行了 ", end="")
    if printing.change_type == ChangeType.Add:
        print(f"\033[32m增加\033[0m ,值为 \033[32m{printing.parameter}\033[0m ")
    elif printing.change_type == ChangeType.Update:
        print(f"\033[32m修改\033[0m,修改后值为 \033[32m{printing.parameter}\033[0m ")
    elif printing.change_type == ChangeType.Delete:
        print(f"\033[32m删除\033[0m")

def isConfigSynced(change_list, check_list):
    if len(change_list) == 0:
        return True

    first_change = change_list[0]

    for config in check_list:
        changed_flag = False

        for change in change_list:
            if config == change.change_file:
                changed_flag = True
                if change != first_change:
                    return False

        if changed_flag == False:
            return False

    return True


class ConfigChecker:
    def __init__(self, changed_files):
        self.changed_files = changed_files
        # ChangesForOnePath的集合
        self.all_changes = set()
        # 字典 key为项目的名字，value为山头对应的mff配置的列表                   
        self.proj_and_its_config_dict = dict() 
        # 所有配置文件的列表
        self.all_config = []
        # 本次commit中改动了的配置文件的列表                   
        self.all_changed_config = set()            

    def run(self):
        # get changes list
        for config in self.all_changed_config:
            self.getChangePath(config)

        too_much_update_flag = False
        if len(self.all_changes) > 10:
            print("==================================================")
            print("您改动的配置项超过十项，为您仅展示可能有问题的改动：")
            print("==================================================")
            too_much_update_flag = True

        for change_for_one_json_path in self.all_changes:
            self.printResult(change_for_one_json_path, too_much_update_flag)


    def printResult(self, change_for_one_json_path:ChangesForOnePath, too_much_update_flag:bool):
        changed_file_for_proj = change_for_one_json_path.classification()

        # 仅修改了一个项目
        if len(changed_file_for_proj.keys()) == 1:
            proj = list(changed_file_for_proj.keys())[0]
            if not too_much_update_flag or not isConfigSynced(changed_file_for_proj[proj], self.proj_and_its_config_dict[proj]):
                print(f"\n您仅在一个项目:\033[32m{proj}\033[0m 中改动了 \033[32m{change_for_one_json_path.json_path}\033[0m 处的配置：")
                for config in self.proj_and_its_config_dict[proj]:
                    changed_flag = False

                    for change in changed_file_for_proj[proj]:
                        if config == change.change_file:
                            changed_flag = True
                            printChangedOperation(change)

                    if changed_flag == False:
                            printNotChangedOperation(config, change_for_one_json_path.json_path)
        # 有多个项目的配置文件被修改
        else:
            if not too_much_update_flag or not isConfigSynced(change_for_one_json_path.change_list, self.all_config):
                print(f"\n您改动了 \033[32m{change_for_one_json_path.json_path}\033[0m 处的配置：")
                for config in self.all_config:
                    changed_flag = False

                    for change in change_for_one_json_path.change_list:
                        if config == change.change_file:
                            changed_flag = True
                            printChangedOperation(change)

                    if changed_flag == False:
                            printNotChangedOperation(config, change_for_one_json_path.json_path)


    def diffPathesCompareJsonToAnother(self, json_object, json_object_compared_to) -> list:
        difference_pathes = []

        current_path = []
        current_path_stack = []
        dfs_stack = []

        dfs_stack.append(json_object)
        current_path_stack.append(current_path)

        while len(dfs_stack) != 0:
            top = dfs_stack[-1]
            dfs_stack.pop()

            top_path = current_path_stack[-1]
            current_path_stack.pop()

            for key,value in top.items():
                current_path = copy.deepcopy(top_path)
                current_path.append(key)
                
                if isinstance(value, dict):
                    dfs_stack.append(value)
                    current_path_stack.append(current_path)
                else:
                    ret = getDictValueFromPath(json_object_compared_to, current_path)
                    if ret == "false" or (ret[0] == 'true' and ret[1] != value):
                        difference_pathes.append(current_path)

        return difference_pathes     

    def addToAllChanges(self, json_path, change_file, opetarion_type:ChangeType, operation_parameter=-1):
        operation = ChangeOperation(change_type=opetarion_type,
                                    parameter=operation_parameter,
                                    change_file=change_file)
        json_path_operation = ChangesForOnePath(json_path)
        json_path_operation.append(operation)
        self.all_changes.add(json_path_operation)

    # 得到一个文件本次commit修改的操作,存储到self.all_changes
    def getChangePath(self, file_name:str) -> list:
        git_cmd = "git show HEAD:" + file_name
        git_cmd_output = subprocess.check_output(git_cmd, shell=True)
        try:
            json_obj_before_change = json.loads(git_cmd_output)
        except Exception as e:
            print(f"\033[31m HEAD: {file_name} JSON解析失败,请检查分支HEAD的该文件是否为合法的json格式\033[0m")
            return
        git_cmd = "git show :" + file_name
        git_cmd_output = subprocess.check_output(git_cmd, shell=True)
        try:
            json_obj_after_change = json.loads(git_cmd_output)
        except Exception as e:
            print(f"\033[31m当前commit: {file_name} JSON解析失败,请检查该文件是否为合法的json格式\033[0m")
            return

        # 将修改后的json相对于修改前的json比较，得到增加和修改的改动
        # 将修改前的json相对于修改后的json比较，得到删除的改动
        add_and_update_operation_pathes = self.diffPathesCompareJsonToAnother(json_obj_after_change, json_obj_before_change)
        for path in add_and_update_operation_pathes:
            value_before = getDictValueFromPath(json_obj_before_change, path)
            value_after = getDictValueFromPath(json_obj_after_change, path)
            # 在修改之前的json中没有该key ==> 该key是新增的
            if value_before == 'false':
                self.addToAllChanges(json_path=path,
                                     opetarion_type=ChangeType.Add,
                                     operation_parameter=value_after[1],
                                     change_file=file_name)
            # 修改前后相同key的value不一样 ==> 该key的value被修改了
            elif value_before[0] == 'true' and value_after[0] == 'true' and value_before[1] != value_after[1]:
                self.addToAllChanges(json_path=path,
                                     opetarion_type=ChangeType.Update,
                                     operation_parameter=value_after[1],
                                     change_file=file_name)

        delete_operation_pathes = self.diffPathesCompareJsonToAnother(json_obj_before_change, json_obj_after_change)
        for path in delete_operation_pathes:
            value_after = getDictValueFromPath(json_obj_after_change, path)
            # 在修改之后的json中没有该key ==> 该key是删除的
            if value_after == 'false':
                self.addToAllChanges(json_path=path,
                                     opetarion_type=ChangeType.Delete,
                                     change_file=file_name)

    def getAllFilePaths(self, directory):
        for root, dirs, files in os.walk(directory):
            for file in files:
                yield os.path.join(root, file)

    # 初始化 proj_and_its_config_dict,all_config,all_changed_config
    def initCheckList(self) -> dict:
        for proj in PROJ:
            self.proj_and_its_config_dict[proj] = list()

        for proj in self.proj_and_its_config_dict.keys():
            for file_path in self.getAllFilePaths("adaptor/" + proj):
                match = re.search(CONFIG_PATTERN, file_path)
                if match:
                    self.proj_and_its_config_dict[proj].append(file_path)
                    self.all_config.append(file_path)

        for file in self.changed_files:
            if file in self.all_config:
                self.all_changed_config.add(file)


if __name__ == "__main__":
    try:
        git_cmd = "git diff --name-only --cached --diff-filter=M"
        git_diff_cmd_output = subprocess.check_output(git_cmd, shell=True)
        git_diff_output_str = git_diff_cmd_output.decode('utf-8')

        changed_files = []
        for file in  git_diff_output_str.splitlines():
            changed_files.append(file)

        checker = ConfigChecker(changed_files)
        checker.initCheckList()

        # 没有修改配置文件则不进行后续的检查
        if len(checker.all_changed_config) == 0:
            exit(0)

        # 检查config
        checker.run()

        # the hook is not running in an interactive environment.
        # make STDIN get input from keyboard manually, and recover STDIN later
        original_stdin = sys.stdin
        try:
            sys.stdin = open("/dev/tty", "r")
            
            print(f"\033[31m\n============================================\033[0m")
            print(f"\033[31m请确认改动是否已经同步到所有应修改的配置文件\033[0m")
            print(f"\033[31m============================================\033[0m")
            print("是否继续commit:")
            while(True):
                user_input = input("   请输入y/n: ")
                if user_input == "y" or user_input == "Y":
                    sys.stdin = original_stdin
                    exit(0)
                elif user_input == "n" or user_input == "N":
                    sys.stdin = original_stdin
                    exit(1)
        except Exception as e1:
            sys.stdin = original_stdin
            raise Exception("error in interacing")

    except Exception as e2:
        traceback.print_exc()
        print(f"\033[31m\n[Error happened in Pre-Commit git hook @ekko.liu]\033[0m")
        print("\n此次commit依然通过")