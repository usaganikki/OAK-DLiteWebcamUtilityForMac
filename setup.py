from setuptools import setup, Extension
from Cython.Build import cythonize
import os

# C99標準を指定 (macOSのclangでは通常不要だが、明示する場合)
# os.environ["CFLAGS"] = "-std=c99"

iokit_wrapper_module = Extension(
    "src.iokit_wrapper", # パッケージ構造に合わせて 'src.iokit_wrapper' とする
    sources=["src/iokit_wrapper.pyx"],
    extra_link_args=['-framework', 'IOKit', '-framework', 'CoreFoundation'],
    # extra_compile_args=["-std=c99"] # こちらに書くことも可能
)

setup(
    name="OAKDLiteWebcamUtility", # プロジェクト名に合わせて変更
    version="0.1.0", # バージョン
    description="IOKit wrapper for OAK-D Lite Webcam Utility",
    ext_modules=cythonize(
        [iokit_wrapper_module],
        compiler_directives={'language_level': "3"} # Python 3互換
    ),
    packages=['src'], # srcディレクトリをパッケージとして認識させる
    # install_requires=[ # Pythonの依存関係があればここに記述
    #     'cython',
    # ],
    zip_safe=False, # Cython拡張モジュールを含む場合はFalse推奨
)
