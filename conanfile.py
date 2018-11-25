from conans import ConanFile, CMake, tools,MSBuild, AutoToolsBuildEnvironment
from shutil import copyfile
import os
from conanos.build import config_scheme




def replace_file(input , output, var={}):
    '''Copies an <input> file to an <output> file and substitutes variable values in var
    '''
    f = open(input)
    content = open(input).read()
    f.close()

    lines = []
    for line in content.splitlines():
        for key ,val in var.items():
            line = line.replace(key,val)
        lines.append(line)

    try:
        os.makedirs(os.path.dirname(output))
    except:
        pass

    f = open(output,'w')
    f.write("\n".join(lines))
    f.close()



class LibtheoraConan(ConanFile):
    name = "libtheora"
    version = "1.1.1"
    description = "A free and open video compression format from the Xiph.org Foundation"
    url = "https://github.com/conanos/libtheora"
    homepage = 'https://www.theora.org/'
    license = "BSD"
    exports = ["LICENSE.md",'theora.def']
    settings = "os", "compiler", "build_type", "arch"
    options = {"shared": [True, False]}
    default_options = "shared=True"
    generators = "cmake"
    requires = "libogg/1.3.3@conanos/stable", "libvorbis/1.3.6@conanos/stable"

    source_subfolder = "source_subfolder"


    def config_options(self):
        del self.settings.compiler.libcxx
        if self.settings.os == 'Windows':
            del self.options.fPIC

    def configure(self):
        config_scheme(self)

    def source(self):
        url_ = 'http://downloads.xiph.org/releases/theora/{name}-{version}.tar.gz'.format(name=self.name, version=self.version)
        tools.get(url_)
        #extracted_dir = self.name + "-" + self.version
        #os.rename(extracted_dir, self.source_subfolder)

        def_ =os.path.join(self.source_subfolder, 'lib','theora.def')
        if not os.path.exists(def_):
            copyfile('theora.def',def_)

        #with tools.chdir(os.path.join(self.source_subfolder, 'lib')):
        #    # file somehow missed in distribution
        #    tools.download('https://raw.githubusercontent.com/xiph/theora/master/lib/theora.def', 'theora.def')






    def build(self):
        if self.settings.compiler == 'Visual Studio':
            self.build_msvc()
        else:
            #self.build_configure()
            self.gcc_build()

    def build_msvc(self):
        # error C2491: 'rint': definition of dllimport function not allowed
        tools.replace_in_file(os.path.join(self.source_subfolder, 'examples', 'encoder_example.c'),
                              'static double rint(double x)',
                              'static double rint_(double x)')

        def format_libs(libs):
            return ' '.join([l + '.lib' for l in libs])

        # fix hard-coded library names
        for project in ['encoder_example', 'libtheora', 'dump_video']:
            for config in ['dynamic', 'static']:
                vcvproj = '%s_%s.vcproj' % (project, config)
                tools.replace_in_file(os.path.join(self.source_subfolder, 'win32', 'VS2008', project, vcvproj),
                                      'libogg.lib',
                                      format_libs(self.deps_cpp_info['libogg'].libs), strict=False)
                tools.replace_in_file(os.path.join(self.source_subfolder, 'win32', 'VS2008', project, vcvproj),
                                      'libogg_static.lib',
                                      format_libs(self.deps_cpp_info['libogg'].libs), strict=False)
                tools.replace_in_file(os.path.join(self.source_subfolder, 'win32', 'VS2008', project, vcvproj),
                                      'libvorbis.lib',
                                      format_libs(self.deps_cpp_info['libvorbis'].libs), strict=False)
                tools.replace_in_file(os.path.join(self.source_subfolder, 'win32', 'VS2008', project, vcvproj),
                                      'libvorbis_static.lib',
                                      format_libs(self.deps_cpp_info['libvorbis'].libs), strict=False)

        with tools.chdir(os.path.join(self.source_subfolder, 'win32', 'VS2008')):
            sln = 'libtheora_dynamic.sln' if self.options.shared else 'libtheora_static.sln'
            msbuild = MSBuild(self)
            msbuild.build(sln, upgrade_project=True, platforms={'x86': 'Win32', 'x86_64': 'x64'})

    def build_configure(self):
        def chmod_plus_x(name):
            os.chmod(name, os.stat(name).st_mode | 0o111)
        with tools.chdir(self.source_subfolder):
            chmod_plus_x('configure')
            configure_args = ['--disable-examples']
            if self.options.shared:
                configure_args.extend(['--disable-static', '--enable-shared'])
            else:
                configure_args.extend(['--disable-shared', '--enable-static'])
            env_build = AutoToolsBuildEnvironment(self)
            if self.settings.os != 'Windows':
                if self.options.fPIC:
                    configure_args.append('--with-pic')
                env_build.pic = self.options.fPIC
            env_build.configure(args=configure_args)
            env_build.make()
            env_build.install()





    def gcc_build(self):
        with tools.chdir(self.source_subfolder):
            with tools.environment_append({
                'PKG_CONFIG_PATH':'%s/lib/pkgconfig:%s/lib/pkgconfig'
                %(self.deps_cpp_info["libogg"].rootpath,self.deps_cpp_info["libvorbis"].rootpath)
                }):

                _args = ['--prefix=%s/builddir'%(os.getcwd()), '--libdir=%s/builddir/lib'%(os.getcwd()),'--disable-maintainer-mode',
                         '--disable-silent-rules','--disable-spec','--disable-doc']
                if self.options.shared:
                    _args.extend(['--enable-shared=yes','--enable-static=no'])
                else:
                    _args.extend(['--enable-shared=no','--enable-static=yes'])

                self.run('./configure %s'%(' '.join(_args)))#space
                self.run('make -j2')
                self.run('make install')

    def package(self):
        if tools.os_info.is_linux:
            with tools.chdir(self.source_subfolder):
                self.copy("*", src="%s/builddir"%(os.getcwd()))

        if self.settings.compiler == 'Visual Studio':
            include_folder = os.path.join(self.source_subfolder, "include")
            self.copy(pattern="*.h", dst="include", src=include_folder)
            self.copy(pattern="*.dll", dst="bin", keep_path=False)
            self.copy(pattern="*.lib", dst="lib", keep_path=False)

            replace_file(os.path.join(self.source_subfolder,'theora.pc.in'),
                         os.path.join(self.package_folder,'lib/pkgconfig/theora.pc'),
                         var={'@prefix@':os.path.abspath(self.package_folder).replace("\\", "/").lower(),
                              '@exec_prefix@':r'${prefix}/bin',
                              '@libdir@':r'${prefix}/lib',
                              '@includedir@':r'${prefix}/include',
                              '@VERSION@':'1.2.3'})


    def package_info(self):
        self.cpp_info.libs = tools.collect_libs(self)





