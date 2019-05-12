#! /usr/bin/python
# -*- coding: utf-8 -*-

# Copyright 2018 Pascal COMBES <pascom@orange.fr>
#
# This file is part of qtcreator-deptree.
#
# qtcreator-deptree is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# qtcreator-deptree is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with qtcreator-deptree. If not, see <http://www.gnu.org/licenses/>

from __future__ import print_function

from enum import Enum
import re
import os
import sys
import subprocess

class DependencyType(Enum):
    """
        Type of dependencies:
            -Unknown when the dependency is of unknown type.
            -Lib for libraries dependencies
            -Plugin for plugin dependencies
    """
    Unknown = 0
    Lib = 1
    Plugin = 2
    
class Dependency:
    """ Base class for dependencies.
    
    Attributes:
        -name: The name of the dependency.
        -type: The type of the dependency.
        -folderName: The name of the folder of the dependency
        -hasExports: The dependency exports symbols
        -deps: Dependencies of this library or plugin
        -preds: Libraries and plugins depending on this dependency
        -transPreds: Libraries or plugins depending transitively on this dependency
        -transDeps: Transitive library or plugin dependencies 
    Methods:
        -addDeps: Adds dependencies 
    """
    def __init__(self, name=""):
        """ Constructor
            
            @param name The name of the dependency.
        """
        self.name = name
        self.type = DependencyType.Unknown
        self.folderName = name
        self.hasExports = False
        self.deps = set()
        self.preds = set()
        self.transDeps = set()
        self.transPreds = set()
    
    def __repr__(self):
        """ Pretty print the dependency """
        return "<Dependency '{}' {}>".format(self.name, list(self.deps))
    
    def packageName(self):
        """ Give the name of the package for the dependency """
        if self.type is DependencyType.Lib:
            if self.name.lower().startswith("lib"):
                return "lib-{}".format(self.name[3:].lower())
            return "lib-{}".format(self.name.lower())
        if self.type is DependencyType.Plugin:
            if self.name.lower().endswith("plugin"):
                return "plugin-{}".format(self.name[:-6].lower())
            return "plugin-{}".format(self.name.lower())
        return self.name.lower()
    
    def addDeps(self, deps):
        """ Add library dependencies 
        
        @param deps : Dependencies which will be added.        
        """
        deps = [d for d in deps if d != ""]
        if deps:
            self.deps = self.deps.union(set(deps))
        
    def getAllDependencies(self):
        """ Returns all dependencies including transitive ones """
        return self.deps.union(self.transDeps)
    
    def getNonTransitiveDependencies(self):
        return self.deps.difference(self.transDeps)
               
    def getAllPredecessors(self):
        """ Returns all predecessors including transitive ones """
        return self.preds.union(self.transPreds) 

    def parseDepPath(self, depPath):
        with open(os.devnull, 'wb') as devNull:
            grep = subprocess.Popen(["grep", "-R", "EXPORT", depPath], stdout=devNull)
            if (grep.wait() == 0):
                self.hasExports = True

    def parseDepFile(self, depFilePath):
        reSpaces = re.compile(r" +")
        reLibName = re.compile(r"^QTC_LIB_NAME *= *")
        reLibDepends = re.compile(r"^QTC_LIB_DEPENDS *\+?= *")
        rePluginName = re.compile(r"^QTC_PLUGIN_NAME *= *")
        rePluginDepends = re.compile(r"^QTC_PLUGIN_DEPENDS *\+?= *")

        with open(depFilePath, "r") as depFile:
            line = depFile.readline()
            while line:
                line = line.strip()
                if len(line) != 0:
                    while line[-1] == "\\":
                        line = line[0:-1] + " " + depFile.readline().strip()
                    if self.type is DependencyType.Lib and reLibName.match(line):
                        self.name = reLibName.sub("", line)
                    if self.type is DependencyType.Plugin and rePluginName.match(line):
                        self.name = rePluginName.sub("", line)
                    if reLibDepends.match(line):
                        self.addDeps(reSpaces.split(reLibDepends.sub("", line).strip()))
                    if self.type is DependencyType.Plugin and rePluginDepends.match(line):
                        self.addDeps(reSpaces.split(rePluginDepends.sub("", line).strip()))
                line = depFile.readline()
 
class Library(Dependency):
    """ Library dependency
    
    Attributes:
        -type (inherited from Dependency): DependencyType.Lib.
    """
    def __init__(self, name=""):
        """ Constructor
            
        @param name The name of the dependency.
        """
        Dependency.__init__(self, name)
        self.type = DependencyType.Lib

    def __repr__(self):
        """ Pretty print the library dependency """
        return "<Library '{}' {}>".format(self.name, list(self.deps))

            
class Plugin(Dependency):
    """ Plugin dependency
    
    Attributes:
        -type (inherited from Dependency): DependencyType.Plugin.
    """
    def __init__(self, name=""):
        """ Constructor
            
        @param name The name of the dependency.
        """
        Dependency.__init__(self, name)
        self.type = DependencyType.Plugin
        
    def __repr__(self):
        """ Pretty print the plugin dependency """
        return "<Plugin '{}' {}>".format(self.name, list(self.deps))

class SourceTreeParser:
    def __init__(self, root=None):
        self.libDir = os.path.join(root, "src", "libs") if (root is not None) else None
        self.pluginDir = os.path.join(root, "src", "plugins") if (root is not None) else None
        self.deps = {}
        self.selected = []
        self.unselected = []
        self.repo = None

        self.requires = {}
        self.develRequires = {}
        self.recommends = {}
        self.develRecommends = {}
        self.provides = {}
        self.develProvides = {}
        self.files = {}
        self.develFiles = {}


    def isOutput(self, dep):
        """ Should the dependency be output

        @param dep A dependency object or its name
        @returns Whether the dependen should be output
        """
        if type(dep) is not str:
            dep = dep.name
        dep = dep.lower()
        return (dep in self.selected) or ((len(self.selected) == 0) and (dep not in self.unselected))

    def parse(self, optimize=True):
        """ Parses Qt Creator dependency tree

        @param optimize Whether transitive dependencies should be optimized, defaults to true.
        @returns None
        """

        # Parse dependency files
        for l in [d for d in os.listdir(self.libDir) if os.path.isdir(os.path.join(self.libDir, d))]:
            self.__parseDependency(l, DependencyType.Lib)
        for p in [d for d in os.listdir(self.pluginDir) if os.path.isdir(os.path.join(self.pluginDir, d))]:
            self.__parseDependency(p, DependencyType.Plugin)
        #print(self.deps)

        # Warshall algorithm
        if (optimize):
            for n in self.deps.keys():
                self.__updatePredecessors(n)
            for d in self.deps.values():
                self.__updateTransitiveClosure(d)

    def outputDot(self, dotFilePath, outputLibs=True, outputPlugins=True, outputAllDeps=False):
        """ Output dependencies as a .dot graph

        @param dotFilePath : The path to the .dot file.
        @param outputLibs: Whether libs are output.
        @param outputPlugins: Whether plugins are output.
        @param outputAllDeps: Whether all deps found in dependencies.pri files are shown.
        """
        with open(dotFilePath, "w") as dotFile:
            dotFile.write("digraph deps {\n")
            dotFile.write("    node [shape=box]\n")
            if outputLibs:
                for n, l in self.deps.items():
                    if (l.type is DependencyType.Lib) and self.isOutput(l):
                        dotFile.write("    {} [label=\"{}\"]\n".format(n, l.name))
            dotFile.write("    node [shape=box, style=rounded]\n")
            if outputPlugins:
                for n, p in self.deps.items():
                    if (p.type is DependencyType.Plugin) and self.isOutput(p):
                        dotFile.write("    {} [label=\"{}\"]\n".format(n, p.name))
            for n, d in self.deps.items():
                if self.isOutput(d) and ((outputLibs and d.type is DependencyType.Lib) or \
                                         (outputPlugins and d.type is DependencyType.Plugin)):
                    for s in d.getNonTransitiveDependencies():
                        if (outputLibs and self.deps[s].type is DependencyType.Lib) or \
                           (outputPlugins and self.deps[s].type is DependencyType.Plugin):
                            dotFile.write("    {} -> {}\n".format(n, s))
            if outputAllDeps:
                dotFile.write("    edge [style=dashed]\n")
                for n, d in self.deps.items():
                    if self.isOutput(d) and ((outputLibs and d.type is DependencyType.Lib) or \
                                             (outputPlugins and d.type is DependencyType.Plugin)):
                        for s in d.deps.difference(d.getNonTransitiveDependencies()):
                            if (outputLibs and self.deps[s].type is DependencyType.Lib) or \
                               (outputPlugins and self.deps[s].type is DependencyType.Plugin):
                                dotFile.write("    {} -> {}\n".format(n, s))
            dotFile.write("}")

    def listDepLibraries(self, outputLibs=True, outputPlugins=True):
        for d in self.deps.values():
            if outputLibs and self.isOutput(d) and (d.type is DependencyType.Lib):
                print("%{{_libdir}}/qtcreator/lib{}.so*".format(d.name))
            if outputPlugins and self.isOutput(d) and (d.type is DependencyType.Plugin):
                print("%{{_libdir}}/qtcreator/plugins/lib{}.so".format(d.name))

    def printMetadata(self, outputLibs=True, outputPlugins=True, file=None):
        for d in self.deps.values():
            if self.isOutput(d) and ((outputLibs and (d.type is DependencyType.Lib)) or \
                                     (outputPlugins and (d.type is DependencyType.Plugin))):
                print("%package {}".format(d.packageName()), file=file)
                print("Summary:    ", end='', file=file)
                self.repo.printSummary(d.packageName(), file=file)
                for s in d.getNonTransitiveDependencies():
                    print("Requires:   qtcreator-{} = %{{version}}".format(self.deps[s].packageName()), file=file)
                self.__printExtra(d, 'requires',   "Requires:   ", file=file)
                self.__printExtra(d, 'provides',   "Provides:   ", file=file)
                self.__printExtra(d, 'recommends', "recommends: ", file=file)
                #if d.name.lower() == "qbsprojectmanager":
                #    print("Requires:   qtcreator-qbs = %{version}", file=file)
                print("", file=file)
                print("%description {}".format(d.packageName()), file=file)
                self.repo.printDescription(d.packageName(), file=file)
                print("", file=file)

    def printDevelMetadata(self, outputLibs=True, outputPlugins=True, file=None):
        for d in self.deps.values():
            if d.hasExports and self.isOutput(d) and ((outputLibs and (d.type is DependencyType.Lib)) or \
                                                      (outputPlugins and (d.type is DependencyType.Plugin))):
                print("%package -n qtcreator-{}-devel".format(d.packageName()), file=file)
                print("Summary:    ", end='', file=file)
                self.repo.printSummary(d.packageName() + '-devel',
                                       "Development files for qtcreator-{}".format(d.packageName()), file=file)
                print("Requires:   qtcreator-devel = %{version}", file=file)
                print("Requires:   qtcreator-{} = %{{version}}".format(d.packageName()), file=file)
                for s in d.getNonTransitiveDependencies():
                    print("Requires:   qtcreator-{}-devel = %{{version}}".format(self.deps[s].packageName()), file=file)
                self.__printExtra(d, 'develRequires',   "Requires:   ", file=file)
                self.__printExtra(d, 'develProvides',   "Provides:   ", file=file)
                self.__printExtra(d, 'develRecommends', "recommends: ", file=file)
                print("", file=file)
                print("%description -n qtcreator-{}-devel".format(d.packageName()), file=file)
                self.repo.printDescription(d.packageName() + '-devel',
                                           """This package contains the files needed to compile a Qt Creator lib or plugin
involving library {}.""".format(d.name), file=file)
                print("", file=file)

    def printFiles(self, outputLibs=True, outputPlugins=True, file=None):
        for d in self.deps.values():
            if self.isOutput(d) and ((outputLibs and (d.type is DependencyType.Lib)) or \
                                     (outputPlugins and (d.type is DependencyType.Plugin))):
                print("%files {}".format(d.packageName()), file=file)
                print("%defattr(-, root, root)", file=file)
                if (d.type is DependencyType.Lib):
                    print("%{{_libdir}}/qtcreator/lib{}.so*".format(d.name), file=file)
                elif (d.type is DependencyType.Plugin):
                    print("%{{_libdir}}/qtcreator/plugins/lib{}.so".format(d.name), file=file)
                self.__printExtra(d, 'files', file=file)
                print("", file=file)

    def printDevelFiles(self, outputLibs=True, outputPlugins=True, file=None):
        for d in self.deps.values():
            if d.hasExports and self.isOutput(d) and ((outputLibs and (d.type is DependencyType.Lib)) or \
                                                      (outputPlugins and (d.type is DependencyType.Plugin))):
                print("%files -n qtcreator-{}-devel".format(d.packageName()), file=file)
                print("%defattr(-, root, root)", file=file)
                if (d.type is DependencyType.Lib):
                    print("%dir %{_includedir}/qtcreator/src/libs", file=file)
                    print("%{{_includedir}}/qtcreator/src/libs/{}".format(d.folderName), file=file)
                else:
                    print("%dir %{_includedir}/qtcreator/src/plugins", file=file)
                    print("%{{_includedir}}/qtcreator/src/plugins/{}".format(d.folderName), file=file)
                self.__printExtra(d, 'develFiles', file=file)
                print("", file=file)

    def __printExtra(self, dep, attr, prefix='', suffix='', file=None):
        extra = getattr(self, attr, {})
        try:
            for item in extra[dep.name.lower()]:
                print(prefix + item + suffix, file=file)
        except(KeyError):
            pass

    def __parseDependency(self, depName, depType = DependencyType.Unknown):
        """ Parses Qt Creator dependency

        @param depName: The name of the dependency (i.e. the name of the directory)
        @param depPath: The path of the dependency (including the name of the dependency).
        It must be an existing path.
        @param depType: The type of dependency.
        It must not be unknown.
        @returns None
        """

        assert(depType is not DependencyType.Unknown)

        if (depType is DependencyType.Lib):
            dep = Library()
            depPath = os.path.join(self.libDir, depName)
        if (depType is DependencyType.Plugin):
            dep = Plugin()
            depPath = os.path.join(self.pluginDir, depName)
        assert(os.path.exists(depPath))
        dep.folderName = os.path.basename(depName)

        # Check if dependency has exports:
        dep.parseDepPath(depPath)

        # Check if it is really a Qt Creator dependency:
        if not os.path.exists(os.path.join(depPath, depName + "_dependencies.pri")) or \
           not os.path.isfile(os.path.join(depPath, depName + "_dependencies.pri")):
            print("Could not find \"{}_dependencies.pri\" in {}".format(depName, depPath))
            return

        # Parses _dependencies.pri file:
        dep.parseDepFile(os.path.join(depPath, depName + "_dependencies.pri"))
        if (len(dep.name) == 0):
            print("Could not find dependency name for \"{}\"".format(depName))
            return
        print(dep)
        # Add dependency to list
        assert(depName not in self.deps)
        self.deps[depName] = dep

    def __updatePredecessors(self, name):
        """ Updates the predecessor list of a dependency

        @param name The name of the dependency to be added in predecessor list
        """
        rm = set()
        for d in self.deps[name].deps:
            try:
                self.deps[d].preds.add(name)
            except (KeyError) as e:
                if (e.args[0] == d):
                    rm.add(d)
                else:
                    raise(e)
        self.deps[name].deps -= rm

    def __updateTransitiveClosure(self, dep):
        """ Updates the transitive closure around a dependency

        @param dep The dependency where the transitive closure should be updated
        """
        for s in dep.getAllDependencies():
            for p in dep.getAllPredecessors():
                self.deps[p].transDeps.add(s)
                self.deps[s].transPreds.add(p)
