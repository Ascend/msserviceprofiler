# Community Outreach Guide: How to Submit an Extension

This document describes how to submit third-party plug-ins or configuration solutions to the msServiceProfiler community and how to process the applications after approval.

--------------------

## Preparations

### 1. Meet the requirements for collection

 * Code is hosted in public repositories (such as GitCode/GitHub/GitLab/Gitee).
 * The warehouse contains`LICENSE`or clear license instructions
 * With basic README (purpose and usage)
 * Related to the application scenario of msServiceProfiler
 * At least one version or configuration description available

### 2. Licensing Recommendations

| Type      | Common Licenses                                                                                               |
| --------- | ------------------------------------------------------------------------------------------------------------- |
| recommend | MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause                                                                   |
| Note:     | GPL-3.0, AGPL-3.0 (Derivative works may need to be open source)                                               |
| Avoidance | No explicit license, commercial closed source (unless free/open source part is available and clearly written) |

--------------------

## Submission Process

1. **Creating an Issue**
    Opens[Issue page of the current warehouse](https://gitcode.com/Ascend/msserviceprofiler/issues)    , click New and select the Extended Submission template (Extended Submission Template).
2. **Filling in the template**
    Fill in the following information based on the template: extension name, description, repository link, license, category (plug-in/configuration scheme/other), and maintainer. (Optional) Enter the version, compatibility, and document/screenshot link.
3. **Waiting for review**
    The maintainer will reply to this issue within one to three working days. If you need to add or modify the information, please update or reply in the same issue.
4. **After passing**
    After the application is approved, the maintainer manually adds the extended information.[Community extension and plug-in list](community_extensions.md)    In the corresponding classification table of.

--------------------

## Reference for Filling Information

Fields in the template and an example (consistent with the Issue template):

```yaml
Extension Name: "my-profiler-plugin"
One-sentence description: "Provides the configuration template for the XXX scenario for msServiceProfiler."
Complete Description: "Describes the functions, application scenarios. andrelationship with msServiceProfiler."

Address: "https://gitcode.com/username/repo"
License Type: "MIT"

Categorize: "plug-in"   #or configuration scheme/other
Maintainer: "@yourusername"
```

Optional: Current version, compatible msServiceProfiler version, dependencies, documentation/demo links.

--------------------

## Audit criteria

| Dimension       | By requesting                                                | Circumstances of possible rejection             |
| --------------- | ------------------------------------------------------------ | ----------------------------------------------- |
| completeness    | The required information is complete and accessible          | Lack of warehouse, license, description, etc.   |
| relevancy       | Related to the application scenario of the msServiceProfiler | Not related to the project                      |
| Licensed        | Clear open source license                                    | No license or not specified                     |
| Maintainability | Readme, comprehensible use                                   | No description, unable to determine the purpose |

--------------------

## Update included extensions

If your extension has been included, you need to update the description, link, or version:

1. Reply to the originally submitted issue. (If the issue has been closed, you can open a new issue and specify the original issue or extension.)
2. Describe the updates (e.g., new version number, new link, description changes)
3. Maintainers will updatecommunity_extensions.mdCorresponding item in

--------------------

## Remove Extension

The maintainer may remove the extension from the list when:

 * Deleted or set the warehouse as private
 * No update for a long time (e.g., more than two years) and the availability cannot be confirmed.
 * The license does not meet the requirements for inclusion after the change.
 * There are security or compliance issues
 * The author explicitly requested removal

--------------------

*If you have any questions, submit an issue in the warehouse and select an appropriate type for consultation.*
