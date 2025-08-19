#include <gtest/gtest.h>

#include <android-base/file.h>
#include <android-base/stringprintf.h>

#include "android_internal.h"
#include "label_internal.h"

using android::base::StringPrintf;
using android::base::WriteStringToFile;
using std::string;

class AndroidSELinuxTest : public ::testing::Test {
    protected:
	TemporaryDir tdir_;
};

TEST_F(AndroidSELinuxTest, LoadAndLookupServiceContext)
{
	string service_contexts =
		StringPrintf("%s/service_contexts", tdir_.path);
	string unused_service_contexts =
		StringPrintf("%s/unused_contexts", tdir_.path);
	string vendor_contexts =
		StringPrintf("%s/vendor_service_contexts", tdir_.path);

	WriteStringToFile("account  u:object_r:account_service:s0\n",
			  service_contexts);
	WriteStringToFile("ignored  u:object_r:ignored_service:s0\n",
			  unused_service_contexts);
	WriteStringToFile(
		"android.hardware.power.IPower/default  u:object_r:hal_power_service:s0\n",
		vendor_contexts);

	const path_alts_t service_paths = { .paths = {
		{ service_contexts.c_str(), unused_service_contexts.c_str() },
		{ vendor_contexts.c_str() }
	}};

	struct selabel_handle *handle = context_handle(
		SELABEL_CTX_ANDROID_SERVICE, &service_paths, "test_service");
	EXPECT_NE(handle, nullptr);

	char *tcontext;
	EXPECT_EQ(selabel_lookup_raw(handle, &tcontext, "foobar",
				     SELABEL_CTX_ANDROID_SERVICE),
		  -1);

	EXPECT_EQ(selabel_lookup_raw(handle, &tcontext, "account",
				     SELABEL_CTX_ANDROID_SERVICE),
		  0);
	EXPECT_STREQ(tcontext, "u:object_r:account_service:s0");
	free(tcontext);

	EXPECT_EQ(selabel_lookup_raw(handle, &tcontext, "ignored",
				     SELABEL_CTX_ANDROID_SERVICE),
		  -1);

	EXPECT_EQ(selabel_lookup_raw(handle, &tcontext,
				     "android.hardware.power.IPower/default",
				     SELABEL_CTX_ANDROID_SERVICE),
		  0);
	EXPECT_STREQ(tcontext, "u:object_r:hal_power_service:s0");
	free(tcontext);

	selabel_close(handle);
}

TEST_F(AndroidSELinuxTest, FailLoadingServiceContext)
{
	string service_contexts =
		StringPrintf("%s/service_contexts", tdir_.path);

	WriteStringToFile("garbage\n", service_contexts);

	const path_alts_t service_paths = { .paths = {
		{ service_contexts.c_str() }
	}};

	struct selabel_handle *handle = context_handle(
		SELABEL_CTX_ANDROID_SERVICE, &service_paths, "test_service");
	EXPECT_EQ(handle, nullptr);
}

TEST_F(AndroidSELinuxTest, LoadAndLookupSeAppContext)
{
	string seapp_contexts =
		StringPrintf("%s/seapp_contexts", tdir_.path);

	WriteStringToFile(
		"# some comment\n"
		"user=_app seinfo=platform domain=platform_app type=app_data_file levelFrom=user\n",
	seapp_contexts);

	const path_alts_t seapp_paths = { .paths = {
		{ seapp_contexts.c_str() }
	}};

	EXPECT_EQ(seapp_context_reload_internal(&seapp_paths), 0);

	context_t ctx = context_new("u:r:unknown");
	int ret = seapp_context_lookup_internal(SEAPP_DOMAIN, 10001, false, "platform", "com.android.test1", ctx);
	EXPECT_EQ(ret, 0);
	EXPECT_STREQ(context_str(ctx), "u:r:platform_app:s0:c512,c768");
	context_free(ctx);

	ctx = context_new("u:r:unknown_data_file");
	ret = seapp_context_lookup_internal(SEAPP_TYPE, 10001, false, "platform", "com.android.test1", ctx);
	EXPECT_EQ(ret, 0);
	EXPECT_STREQ(context_str(ctx), "u:r:app_data_file:s0:c512,c768");
	context_free(ctx);
}

TEST(AndroidSeAppTest, ParseValidSeInfo)
{
	struct parsed_seinfo info;
	memset(&info, 0, sizeof(info));

	string seinfo = "default:privapp:targetSdkVersion=10000:partition=system:complete";
	int ret = parse_seinfo(seinfo.c_str(), &info);

	EXPECT_EQ(ret, 0);
	EXPECT_STREQ(info.base, "default");
	EXPECT_EQ(info.targetSdkVersion, 10000);
	EXPECT_EQ(info.is, IS_PRIV_APP);
	EXPECT_EQ(info.isPreinstalledApp, true);
	EXPECT_STREQ(info.partition, "system");

	seinfo = "platform:ephemeralapp:partition=system:complete";
	ret = parse_seinfo(seinfo.c_str(), &info);

	EXPECT_EQ(ret, 0);
	EXPECT_STREQ(info.base, "platform");
	EXPECT_EQ(info.targetSdkVersion, 0);
	EXPECT_EQ(info.is, IS_EPHEMERAL_APP);
	EXPECT_EQ(info.isPreinstalledApp, true);
	EXPECT_STREQ(info.partition, "system");

	seinfo = "bluetooth";
	ret = parse_seinfo(seinfo.c_str(), &info);

	EXPECT_EQ(ret, 0);
	EXPECT_STREQ(info.base, "bluetooth");
	EXPECT_EQ(info.targetSdkVersion, 0);
	EXPECT_EQ(info.isPreinstalledApp, false);
	EXPECT_EQ(info.is, 0);
}

TEST(AndroidSeAppTest, ParseInvalidSeInfo)
{
	struct parsed_seinfo info;

	string seinfo = "default:targetSdkVersion:complete";
	int ret = parse_seinfo(seinfo.c_str(), &info);
	EXPECT_EQ(ret, -1);

	seinfo = "default:targetSdkVersion=:complete";
	ret = parse_seinfo(seinfo.c_str(), &info);
	EXPECT_EQ(ret, -1);
}

TEST(AndroidSeAppTest, ParseOverflow)
{
	struct parsed_seinfo info;

	string seinfo = std::string(255, 'x');
	int ret = parse_seinfo(seinfo.c_str(), &info);
	EXPECT_EQ(ret, 0);
	EXPECT_STREQ(info.base, seinfo.c_str());

	seinfo = std::string(256, 'x');
	ret = parse_seinfo(seinfo.c_str(), &info);
	EXPECT_EQ(ret, -1);
}

TEST(AndroidSELinuxPathTest, IsAppDataPath)
{
	EXPECT_TRUE(is_app_data_path("/data/data"));
	EXPECT_TRUE(is_app_data_path("/data/user/0"));

	EXPECT_FALSE(is_app_data_path("/data"));
}

TEST(AndroidSELinuxPathTest, IsCredentialEncryptedPath)
{
	EXPECT_TRUE(is_credential_encrypted_path("/data/system_ce/0"));
	EXPECT_TRUE(is_credential_encrypted_path("/data/system_ce/0/backup"));
	EXPECT_TRUE(is_credential_encrypted_path("/data/misc_ce/0"));
	EXPECT_TRUE(is_credential_encrypted_path("/data/misc_ce/0/apexdata"));
	EXPECT_TRUE(is_credential_encrypted_path("/data/vendor_ce/0"));
	EXPECT_TRUE(is_credential_encrypted_path("/data/vendor_ce/0/data"));

	EXPECT_FALSE(is_credential_encrypted_path("/data"));
	EXPECT_FALSE(is_credential_encrypted_path("/data/data"));
	EXPECT_FALSE(is_credential_encrypted_path("/data/user/0"));
}

TEST(AndroidSELinuxPathTest, ExtractPkgnameAndUserid)
{
	char *pkgname = NULL;
	unsigned int userid;

	EXPECT_EQ(extract_pkgname_and_userid("/data/", &pkgname, &userid), -1);

	char const* path = "/data/user/0/com.android.myapp";
	EXPECT_EQ(extract_pkgname_and_userid(path, &pkgname, &userid), 0);
	EXPECT_STREQ("com.android.myapp", pkgname);
	EXPECT_EQ(userid, 0);
	free(pkgname);
	pkgname = NULL;

	path = "/data/user/0/com.android.myapp/som/subdir";
	EXPECT_EQ(extract_pkgname_and_userid(path, &pkgname, &userid), 0);
	EXPECT_STREQ("com.android.myapp", pkgname);
	EXPECT_EQ(userid, 0);
	free(pkgname);
	pkgname = NULL;

	path = "/data/data/com.android.myapp2";
	EXPECT_EQ(extract_pkgname_and_userid(path, &pkgname, &userid), 0);
	EXPECT_STREQ("com.android.myapp2", pkgname);
	EXPECT_EQ(userid, 0);
	free(pkgname);
	pkgname = NULL;

	path = "/data/misc_de/10/sdksandbox/com.android.myapp3";
	EXPECT_EQ(extract_pkgname_and_userid(path, &pkgname, &userid), 0);
	EXPECT_STREQ("com.android.myapp3", pkgname);
	EXPECT_EQ(userid, 10);
	free(pkgname);
	pkgname = NULL;
}
