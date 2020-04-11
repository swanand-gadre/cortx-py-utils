#!/usr/bin/env python3

"""
 ****************************************************************************
 Filename:          genrate.py
 Description:       Genarate HA rule for given HA framework target

 Creation Date:     03/13/2020
 Author:            Ajay Paratmandali

 Do NOT modify or remove this copyright and confidentiality notice!
 Copyright (c) 2001 - $Date: 2015/01/14 $ Seagate Technology, LLC.
 The code contained herein is CONFIDENTIAL to Seagate Technology, LLC.
 Portions are also trade secret. Any use, duplication, derivation, distribution
 or disclosure of this code, for any reason, not expressly authorized is
 prohibited. All other rights are expressly reserved by Seagate Technology, LLC.
 ****************************************************************************
"""

import os
import json
import traceback
import re
import ast
import copy
from string import Template

from eos.utils.schema.conf import Conf
from eos.utils.schema.payload import *
from eos.utils.ha import const

class Generator:
    def __init__(self, compiled_file, output_file, args_file):
        """
        compiled_file   : Compiled file generate by hac compiler
        output_file     : Output file for target ha tool
        args_file       : Provision file for dynamic input
        """
        if compiled_file is None:
            raise Exception("compiled_file is missing")
        if output_file is None:
            raise Exception("output_file is missing")
        if args_file is None:
            raise Exception("args_file is missing")
        self._is_file(compiled_file)
        self._is_file(args_file)
        Conf.load(const.PROV_CONF_INDEX, Yaml(args_file))
        self._script = output_file
        with open(compiled_file, "r") as f:
            self.compiled_json = json.load(f)
            self._modify_schema()
            self._provision_compiled_schema(self.compiled_json)
        self._resource_set = self.compiled_json["resources"]

    def _provision_compiled_schema(self, compiled_schema):
        """
        Scan schema and replace ${var} in compiled schema
        to configuration provided by provision.
        """
        keys = re.findall(r"\${[^}]+}(?=[^]*[^]*)", str(compiled_schema))
        args = {}
        new_compiled_schema = str(compiled_schema)
        for element in keys:
            key = element.replace("${", "").replace("}", "")
            new_compiled_schema = new_compiled_schema.replace(element,
                    str(Conf.get(const.PROV_CONF_INDEX, key, element)))
        self.compiled_json = ast.literal_eval(new_compiled_schema)

    def _is_file(self, filename):
        """
        Check if file exists
        """
        if not os.path.isfile(filename):
            raise Exception("%s invalid file in genarator" %filename)

    def _modify_schema(self):
        pass

    def _cluster_create(self):
        pass

class KubernetesGenerator(Generator):
    def __init__(self, compiled_file, output_file, args_file):
        super(KubernetesGenerator, self).__init__(compiled_file, output_file, args_file)
        pass

    def create_script(self):
        with open(self._script, "w") as script_file:
            script_file.writelines("#!/bin/bash\n\n")
            script_file.writelines("# Create Pod\n")
        self._cluster_create()

    def _cluster_create(self):
        with open(self._script, "a") as script_file:
            for resource in self._resource_set.keys():
                script_file.writelines("kubectl deploy pod "+ resource + ".yaml\n")

class PCSGenerator(Generator):
    def __init__(self, compiled_file, output_file, args_file):
        """
        compiled_file: combined spec file
        output_file: output file generate by Generator
        """
        super(PCSGenerator, self).__init__(compiled_file, output_file, args_file)
        self._cluster_cfg = (output_file.split('/')[len(output_file.split('/'))-1]).replace(".sh", ".xml")
        self._mode = {
            "active_passive": self._create_resource_active_passive,
            "active_active" : self._create_resource_active_active,
            "master_slave": self._create_resource_master_slave
        }

    def create_script(self):
        """
        Create targeted rule file for PCSGenerate
        """
        with open(self._script, "w") as script_file:
            script_file.writelines("#!/bin/bash\n\n")
            script_file.writelines("#Assign variable\n\n")
        self._assign_var()
        with open(self._script, "a") as script_file:
            script_file.writelines("\n\n# Set pcs cluster \n\n")
            script_file.writelines("pcs cluster cib "+self._cluster_cfg+ "\n")
            script_file.writelines("# Create Resource\n")
        self._cluster_create()

    def _assign_var(self):
        """
        Assign value to runtime variable
        """
        keys = list(set(re.findall(r"\${[^}]+}(?=[^]*[^]*)", str(self.compiled_json))))
        args = {}
        with open(self._script, "a") as script_file:
            script_file.writelines("pcs_status=$(pcs constraint)\n")
            script_file.writelines("pcs_location=$(pcs constraint location)\n")
            for element in keys:
                if "." not in element:
                    variable = element.replace("${", "").replace("}", "")
                    key = variable.replace("_", ".")
                    script_file.writelines(variable+ "="+ str(Conf.get(const.PROV_CONF_INDEX, key))+"\n")

    def _pcs_cmd_load(self):
        """
        Contain all command to generate pcs cluster
        """
        self._resource_create = Template("echo $$pcs_status | grep -q $resource || "+
            "pcs -f $cluster_cfg resource create $resource "+
            "$provider $param $metadata "+
            "op monitor timeout=$mon_tout interval=$mon_in op start "+
            "timeout=$sta_tout op stop timeout=$sto_tout")
        self._active_active = Template("echo $$pcs_status | grep -q $resource || "+
            "pcs -f $cluster_cfg resource clone $resource "+
            "clone-max=$clone_max clone-node-max=$clone_node_max $param")
        self._master_slave = Template("echo $$pcs_status | grep -q $resource || "+
            "pcs -f $cluster_cfg resource master $master "+
            "$resource clone-max=$clone_max clone-node-max=$clone_node_max "+
            "master-max=$master_max master-node-max=$master_node_max $param")
        self._location = Template("echo $$pcs_location | grep -q $resource || "+
            "pcs -f $cluster_cfg constraint location $resource prefers $node=$score")
        self._order = Template("echo $$pcs_status | grep -q 'start $res1 then start $res2' || "+
            "pcs -f $cluster_cfg constraint order $res1 then $res2")
        self._colocation = Template("echo $$pcs_status | grep -q 'set $res1 $res2' || "+
            "pcs -f $cluster_cfg constraint colocation set $res1 $res2")

    def _cluster_create(self):
        """
        Create pcs cluster
        """
        try:
            self._pcs_cmd_load()
            for res in self._resource_set.keys():
                res_mode = self._resource_set[res]["ha"]["mode"]
                self._res_create(res, res_mode)
            with open(self._script, "a") as f:
                f.writelines("\n\n#Location\n")
            for res in self._resource_set.keys():
                res_mode = self._resource_set[res]["ha"]["mode"]
                self._create_location(res, res_mode)
            with open(self._script, "a") as f:
                f.writelines("\n\n#Order\n")
            self._create_order()
            with open(self._script, "a") as f:
                f.writelines("\n\n#Colocation\n")
            self._create_colocation()
            with open(self._script, "a") as f:
                f.writelines("pcs cluster verify -V " +self._cluster_cfg+ "\n")
                f.writelines("pcs cluster cib-push " +self._cluster_cfg+ "\n")
        except Exception as e:
            raise Exception(str(traceback.format_exc()))

    def _res_create(self, res, res_mode):
        params = ""
        if "parameters" in self._resource_set[res].keys():
            for parameter in self._resource_set[res]["parameters"].keys():
                params = params + parameter+ "=" +self._resource_set[res]["parameters"][parameter] + " "
        timeout_list = [int(x.replace("s",""))*2 for x in self._resource_set[res]["provider"]["timeouts"]]
        meta_param = ""
        if "metadata" in self._resource_set[res]:
            for meta in self._resource_set[res]["metadata"].keys():
                meta_param = meta_param + meta+ "=" + str(self._resource_set[res]["metadata"][meta]) + " "
        resource = self._resource_create.substitute(
                    cluster_cfg=self._cluster_cfg,
                    resource=res,
                    provider=self._resource_set[res]["provider"]["name"],
                    param=params,
                    mon_tout=self._resource_set[res]["provider"]["timeouts"][1],
                    mon_in=self._resource_set[res]["provider"]["interval"],
                    sta_tout=self._resource_set[res]["provider"]["timeouts"][0],
                    sto_tout=self._resource_set[res]["provider"]["timeouts"][2],
                    metadata="meta " + meta_param
                )
        with open(self._script, "a") as f:
            f.writelines(resource+ "\n")
        self._mode[res_mode](res)
        with open(self._script, "a") as f:
            f.writelines("\n")

    def _create_resource_active_passive(self, res):
        pass

    def _create_resource_active_active(self, res):
        params = ""
        if "parameters" in self._resource_set[res]["ha"]["clones"].keys():
            for parameter in self._resource_set[res][res]["ha"]["clones"]["parameters"].keys():
                params = params + parameter+ "=" +self._resource_set[res]["ha"]["clones"]["parameters"][parameter]
                params = params + " "
        clone = self._active_active.substitute(
            cluster_cfg=self._cluster_cfg,
            resource=res,
            clone_max=self._resource_set[res]["ha"]["clones"]["active"][1],
            clone_node_max=self._resource_set[res]["ha"]["clones"]["active"][0],
            param=params
        )
        with open(self._script, "a") as f:
            f.writelines(clone+ "\n")

    def _create_resource_master_slave(self, res):
        params = ""
        if "parameters" in self._resource_set[res]["ha"]["clones"].keys():
            for parameter in self._resource_set[res][res]["ha"]["clones"]["parameters"].keys():
                params = params + parameter+ "=" +self._resource_set[res]["ha"]["clones"]["parameters"][parameter]
                params = params + " "
        master = self._master_slave.substitute(
            cluster_cfg=self._cluster_cfg,
            master=res+"_Master",
            resource=res,
            clone_max=self._resource_set[res]["ha"]["clones"]["active"][1],
            clone_node_max=self._resource_set[res]["ha"]["clones"]["active"][0],
            master_max=self._resource_set[res]["ha"]["clones"]["master"][1],
            master_node_max=self._resource_set[res]["ha"]["clones"]["master"][0],
            param=params
        )
        with open(self._script, "a") as f:
            f.writelines(master+ "\n")

    def _get_clone_name(self, resource):
        """
        Parse and return clone name
        """
        res_name = ""
        mode = self._resource_set[resource]["ha"]["mode"]
        if mode != "active_passive":
            res_name = resource + ("-clone" if mode == "active_active" else "_Master")
        else:
            res_name = resource
        return res_name

    def _create_order(self):
        with open(self._script, "a") as f:
            for edge in self.compiled_json["predecessors_edge"]:
                r0 = self._get_clone_name(edge[0])
                r1 = self._get_clone_name(edge[1])
                res_order = self._order.substitute(
                    cluster_cfg=self._cluster_cfg,
                    res1=r0,
                    res2=r1
                )
                f.writelines(res_order+ "\n")

    def _create_colocation(self):
        with open(self._script, "a") as f:
            for edge in self.compiled_json["colocation_edges"]:
                r0 = self._get_clone_name(edge[0])
                r1 = self._get_clone_name(edge[1])
                colocation_cmd = self._colocation.substitute(
                    cluster_cfg=self._cluster_cfg,
                    res1=r0,
                    res2=r1
                    )
                f.writelines(colocation_cmd+ "\n")

    def _create_location(self, res, res_mode):
        with open(self._script, "a") as f:
            res_clone = self._get_clone_name(res)
            for node in self._resource_set[res]["ha"]["location"].keys():
                colocation_cmd = self._location.substitute(
                    cluster_cfg=self._cluster_cfg,
                    resource=res_clone,
                    node=node,
                    score=self._resource_set[res]["ha"]["location"][node]
                )
                f.writelines(colocation_cmd+ "\n")

class PCSGeneratorResource(PCSGenerator):

    def __init__(self, compiled_file, output_file, args_file, resources):
        """
        Update schema for perticular resource
        """
        self._resources = resources if resources is None else resources.split()
        super(PCSGeneratorResource, self).__init__(compiled_file, output_file, args_file)

    def _modify_schema(self):
        """
        Modify schema sutaible for less resources
        """
        if self._resources is None:
            return
        for resource in self._resources:
            if resource not in self.compiled_json['resources'].keys():
                raise Exception("Invalid [%s] resource in resources parameter" %resource)
        self._new_compiled_schema = copy.deepcopy(self.compiled_json)
        self._recursive_list = self._resources
        self._search_recursive()
        self._modify_compiled_schema_resources()
        self._update_edge("predecessors_edge")
        self._update_edge("colocation_edges")
        self._update_isolate_resources()
        self.compiled_json = self._new_compiled_schema

    def _search_recursive(self):
        """
        Search all predecessors resources recursivlly
        """
        for resource in self._recursive_list:
            predecessors = self.compiled_json['resources'][resource]['dependencies']['predecessors']
            colocation = self.compiled_json['resources'][resource]['dependencies']['colocation']
            self._recursive_list.extend(predecessors)
            self._recursive_list.extend(colocation)
        self._recursive_list = list(set(self._recursive_list))

    def _modify_compiled_schema_resources(self):
        """
        Remove all unwanted resources from compiled schema
        """
        for resource in self.compiled_json['resources']:
            if resource not in self._recursive_list:
                del self._new_compiled_schema['resources'][resource]

    def _update_edge(self, key):
        """
        Remove edges that not in use
        """
        for edge in self.compiled_json[key]:
            if edge[0] not in self._recursive_list or edge[1] not in self._recursive_list:
                self._new_compiled_schema[key].remove(edge)

    def _update_isolate_resources(self):
        for resource in self.compiled_json['isolate_resources']:
            if resource not in self._recursive_list:
                self._new_compiled_schema['isolate_resources'].remove(resource)
