int start()
{
  __security_init_cookie();
  return __tmainCRTStartup();
  }

  
int __tmainCRTStartup()
{
  int v0; // eax
  CHAR *v1; // eax
  int wShowWindow; // ecx
  int v3; // eax
  struct _STARTUPINFOA StartupInfo; // [esp+10h] [ebp-68h] BYREF
  int v6; // [esp+58h] [ebp-20h]
  BOOL v7; // [esp+5Ch] [ebp-1Ch]
  CPPEH_RECORD ms_exc; // [esp+60h] [ebp-18h]

  ms_exc.registration.TryLevel = 0;
  GetStartupInfoA(&StartupInfo);
  ms_exc.registration.TryLevel = -2;
  v7 = LOWORD(_ImageBase.unused) == 23117
    && *(int *)((char *)&_ImageBase.unused + (_DWORD)off_2E00003C) == 17744
    && *(__int16 *)((char *)&word_2E000018 + (_DWORD)off_2E00003C) == 267
    && *(_DWORD *)&byte_2E000040[(_DWORD)off_2E00003C + 52] > 0xEu
    && *(int *)((char *)&dword_2E0000E8 + (_DWORD)off_2E00003C) != 0;
  if ( !_heap_init(1) )
    fast_error_exit(28);
  if ( !_mtinit() )
    fast_error_exit(16);
  sub_2E03223E();
  ms_exc.registration.TryLevel = 1;
  if ( _ioinit() < 0 )
    _amsg_exit(27);
  dword_2E04C634 = (int)GetCommandLineA();
  Block = (char *)__crtGetEnvironmentStringsA();
  if ( _setargv() < 0 )
    _amsg_exit(8);
  if ( _setenvp() < 0 )
    _amsg_exit(9);
  v0 = _cinit(1);
  if ( v0 )
    _amsg_exit(v0);
  v1 = (CHAR *)_wincmdln();
  if ( (StartupInfo.dwFlags & 1) != 0 )
    wShowWindow = StartupInfo.wShowWindow;
  else
    wShowWindow = 10;
  v3 = WinMain(&_ImageBase, 0, v1, wShowWindow);
  v6 = v3;
  if ( !v7 )
    exit(v3);
  _cexit();
  return v6;
} 



int __stdcall WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPSTR lpCmdLine, int nShowCmd)
{
  char *v4; // eax
  const CHAR *v6; // eax
  const CHAR *v7; // eax
  int v8; // eax
  LPCVOID *v9; // eax
  LPCVOID *v10; // eax
  LPCVOID *v11; // ecx
  LPCVOID *v12; // eax
  int v13; // ebx
  int v14; // [esp-4h] [ebp-174h]
  int v15; // [esp-4h] [ebp-174h]
  int v16; // [esp-4h] [ebp-174h]
  LPCVOID *v17; // [esp-4h] [ebp-174h]
  char *Block; // [esp+10h] [ebp-160h]
  char v19[256]; // [esp+14h] [ebp-15Ch] BYREF
  char v20[74]; // [esp+114h] [ebp-5Ch] BYREF
  char v21; // [esp+15Eh] [ebp-12h]
  char v22; // [esp+15Fh] [ebp-11h]
  int v23; // [esp+16Ch] [ebp-4h]

  sub_2E027090();
  v23 = 1;
  v22 = 0;
  v21 = sub_2E026D68(dword_2E04AB80, dword_2E04AB7C);
  if ( byte_2E04AAE0 )
  {
    LOBYTE(v23) = 2;
    if ( dword_2E049678 )
    {
      v4 = dword_2E049668;
      if ( (unsigned int)dword_2E04967C < 0x10 )
        v4 = (char *)&dword_2E049668;
      sub_2E025F12(byte_2E0494F0, v4);
    }
    else
    {
      sub_2E025F39(byte_2E0494F0);
    }
    v23 = 1;
  }
  sub_2E025E3A("OPatchInstall: Run starts");
  sub_2E025E3A(&dword_2E0012A4);
  sub_2E025E3A("OPatchInstall: Running version ");
  sub_2E025E3A("14.0.6119.0");
  sub_2E025E3A(&dword_2E0012A4);
  if ( !(unsigned __int8)sub_2E028364() )
  {
    sub_2E025E3A("OPatchInstall: Failed to initalize the UNICODE layer");
LABEL_10:
    sub_2E025E3A(&dword_2E0012A4);
    v23 = -1;
    sub_2E027070(v20);
    return -1;
  }
  if ( byte_2E04AAF0 )
    sub_2E025E3A("OPatchInstall: Running on a Unicode OS");
  else
    sub_2E025E3A("OPatchInstall: Running on an ANSI OS");
  sub_2E025E3A(&dword_2E0012A4);
  if ( CoInitialize(0) < 0 )
  {
    sub_2E025E3A("OPatchInstall: CoInitialize failed");
    goto LABEL_10;
  }
  InitCommonControls();
  if ( !(unsigned __int8)sub_2E012F42() )
  {
    sub_2E025E3A("OPatchInstall: CActionInstallMsps::Initialize failed");
    goto LABEL_10;
  }
  if ( !(unsigned __int8)sub_2E0295E4() )
  {
    sub_2E025E3A("OPatchInstall:CCabExtract::Initialize failed");
    goto LABEL_10;
  }
  sub_2E02326B(v20);
  if ( v22 )
    sub_2E021C7D(L"LOGFILE_CREATION_ERROR", "1");
  if ( byte_2E04AAE1 )
  {
    sub_2E0212BA((int)L"SYS.ARGS.QUIET", (__int16)"1");
    sub_2E0212BA((int)L"SYS.ARGS.QUIETREADONLY", (__int16)"1");
  }
  if ( byte_2E04AAE0 )
  {
    sub_2E0212BA((int)L"SYS.ARGS.LOG", (__int16)"1");
    sub_2E0212BA((int)L"SYS.ARGS.LOGREADONLY", (__int16)"1");
    v14 = *(_DWORD *)sub_2E00F8E7(byte_2E0494F0);
    LOBYTE(v23) = 4;
    sub_2E0212BA((int)L"SYS.ARGS.LOGPATH", v14);
    LOBYTE(v23) = 1;
    if ( Block != v19 )
      free(Block);
    sub_2E0212BA((int)L"SYS.ARGS.LOGPATHREADONLY", (__int16)"1");
  }
  if ( byte_2E04AAE5 )
  {
    sub_2E0212BA((int)L"SYS.ARGS.EXTRACT", (__int16)"1");
    sub_2E0212BA((int)L"SYS.ARGS.EXTRACTREADONLY", (__int16)"1");
    if ( dword_2E049694 )
    {
      v6 = lpString;
      if ( (unsigned int)dword_2E049698 < 0x10 )
        v6 = (const CHAR *)&lpString;
      v15 = *(_DWORD *)sub_2E00F8E7(v6);
      LOBYTE(v23) = 5;
      sub_2E0212BA((int)L"SYS.ARGS.EXTRACTPATH", v15);
      LOBYTE(v23) = 1;
      if ( Block != v19 )
        free(Block);
      sub_2E0212BA((int)L"SYS.ARGS.EXTRACTPATHREADONLY", (__int16)"1");
    }
  }
  if ( byte_2E04AAE2 )
  {
    sub_2E0212BA((int)L"SYS.ARGS.PASSIVE", (__int16)"1");
    sub_2E0212BA((int)L"SYS.ARGS.PASSIVEREADONLY", (__int16)"1");
  }
  if ( byte_2E04AAE3 )
  {
    sub_2E0212BA((int)L"SYS.ARGS.NORESTART", (__int16)"1");
    sub_2E0212BA((int)L"SYS.ARGS.NORESTARTREADONLY", (__int16)"1");
  }
  if ( byte_2E04AAE4 )
  {
    sub_2E0212BA((int)L"SYS.ARGS.FORCERESTART", (__int16)"1");
    sub_2E0212BA((int)L"SYS.ARGS.FORCERESTARTREADONLY", (__int16)"1");
  }
  if ( byte_2E04AAE6 )
  {
    sub_2E0212BA((int)L"SYS.ARGS.LANG", (__int16)"1");
    sub_2E0212BA((int)L"SYS.ARGS.LANGREADONLY", (__int16)"1");
    v7 = dword_2E0496A0;
    if ( (unsigned int)dword_2E0496B4 < 0x10 )
      v7 = (const CHAR *)&dword_2E0496A0;
    v16 = *(_DWORD *)sub_2E00F8E7(v7);
    LOBYTE(v23) = 6;
    sub_2E0212BA((int)L"SYS.ARGS.LANGVALUE", v16);
    LOBYTE(v23) = 1;
    if ( Block != v19 )
      free(Block);
    sub_2E0212BA((int)L"SYS.ARGS.LANGVALUEREADONLY", (__int16)"1");
  }
  if ( dword_2E049628 != -1 )
  {
    sub_2E025E3A("OPatchInstall: Setting argument properties");
    sub_2E025E3A(&dword_2E0012A4);
    if ( !(unsigned __int8)sub_2E026BCF(dword_2E04AB80, dword_2E04AB7C, dword_2E049628, v20) )
    {
      sub_2E025E3A("OPatchInstall: Invalid property definition passed");
      sub_2E025E3A(&dword_2E0012A4);
LABEL_52:
      sub_2E025E3A("OPatchInstall: Will show the help message");
      sub_2E025E3A(&dword_2E0012A4);
      sub_2E0212BA((int)L"SYS.ARGS.HELP", (__int16)"1");
      sub_2E0212BA((int)L"SYS.ARGS.HELPREADONLY", (__int16)"1");
      goto LABEL_53;
    }
    sub_2E025E3A("OPatchInstall: Done setting argument properties");
    sub_2E025E3A(&dword_2E0012A4);
  }
  if ( !v21 )
    goto LABEL_52;
LABEL_53:
  sub_2E025E3A("OPatchInstall: Script execution starts");
  sub_2E025E3A(&dword_2E0012A4);
  if ( dword_2E049640 )
  {
    if ( dword_2E04965C )
    {
      v11 = (LPCVOID *)lpBuffer;
      if ( (unsigned int)dword_2E049660 < 0x10 )
        v11 = &lpBuffer;
      v12 = (LPCVOID *)dword_2E049630;
      if ( (unsigned int)dword_2E049644 < 0x10 )
        v12 = &dword_2E049630;
      v8 = sub_2E0224EF(v12, v11);
    }
    else
    {
      sub_2E025E3A("OPatchInstall: No manifest file specified, will extract the XML from the exe when present");
      sub_2E025E3A(&dword_2E0012A4);
      v10 = (LPCVOID *)dword_2E049630;
      if ( (unsigned int)dword_2E049644 < 0x10 )
        v10 = &dword_2E049630;
      v8 = sub_2E0224EF(v10, 0);
    }
  }
  else
  {
    sub_2E025E3A("OPatchInstall: No XML specified, will extract the XML from the exe");
    sub_2E025E3A(&dword_2E0012A4);
    if ( dword_2E04965C )
    {
      v9 = (LPCVOID *)lpBuffer;
      if ( (unsigned int)dword_2E049660 < 0x10 )
        v9 = &lpBuffer;
      v17 = v9;
    }
    else
    {
      sub_2E025E3A("OPatchInstall: No manifest file specified, will extract the XML from the exe when present");
      sub_2E025E3A(&dword_2E0012A4);
      v17 = 0;
    }
    v8 = sub_2E0224EF(0, v17);
  }
  v13 = v8;
  sub_2E025E3A("OPatchInstall: Run Ends");
  sub_2E025E3A(&dword_2E0012A4);
  sub_2E025E3A("OPatchInstall: Performing clean up");
  sub_2E025E3A(&dword_2E0012A4);
  sub_2E02773F();
  sub_2E00DBA2();
  sub_2E029AFE();
  sub_2E010427();
  sub_2E012F64();
  sub_2E028412();
  sub_2E025E3A("OpatchInstall: Clean up done");
  sub_2E025E3A(&dword_2E0012A4);
  sub_2E025E3A("OPatchInstall: Run ends");
  sub_2E025E3A(&dword_2E0012A4);
  v23 = -1;
  sub_2E027070(v20);
  return v13;
}