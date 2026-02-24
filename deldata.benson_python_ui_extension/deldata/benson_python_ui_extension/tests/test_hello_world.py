# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

# NOTE:
#   omni.kit.test - std python's unittest module with additional wrapping to add
#   suport for async/await tests
#   For most things refer to unittest docs:
#   https://docs.python.org/3/library/unittest.html
import omni.kit.test

# Extension for writing UI tests (to simulate UI interaction)
import omni.kit.ui_test as ui_test

# Import extension python module we are testing with absolute import path,
# as if we are external user (other extension)
import deldata.benson_python_ui_extension


# Having a test class dervived from omni.kit.test.AsyncTestCase declared on the
# root of module will make it auto-discoverable by omni.kit.test
class Test(omni.kit.test.AsyncTestCase):
    # Before running each test
    async def setUp(self):
        pass

    # After running each test
    async def tearDown(self):
        pass

    # Actual test, notice it is an "async" function, so "await" can be used if needed
    async def test_hello_public_function(self):
        result = deldata.benson_python_ui_extension.some_public_function(4)
        self.assertEqual(result, 256)

    async def test_window_exists(self):
        # Verify frame and a label exist; removed Add/Reset buttons
        ui_test.find("BwnsonDelDataExtension//Frame")
        ui_test.find("BwnsonDelDataExtension//Frame/**/Label[*]")
