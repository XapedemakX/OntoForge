SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Employees](
	[EmployeeID] [int] IDENTITY(1,1) NOT NULL,
	[FirstName] [nvarchar](50) NOT NULL,
	[LastName] [nvarchar](50) NOT NULL,
	[Email] [nvarchar](255) NULL,
	[HireDate] [date] NOT NULL,
	[Salary] [money] NULL,
	[Active] [bit] NOT NULL,
	[ManagerID] [int] NULL,
	[DepartmentID] [int] NOT NULL,
	[RowVer] [timestamp] NOT NULL,
	[Photo] [varbinary](max) NULL,
	[Guid] [uniqueidentifier] NOT NULL,
 CONSTRAINT [PK_Employees] PRIMARY KEY CLUSTERED ([EmployeeID] ASC) WITH (PAD_INDEX = OFF) ON [PRIMARY],
 CONSTRAINT [UQ_Employees_Email] UNIQUE NONCLUSTERED ([Email] ASC)
) ON [PRIMARY]
GO
CREATE TABLE [dbo].[Departments](
	[DepartmentID] [int] NOT NULL,
	[Name] [nvarchar](100) NOT NULL,
 CONSTRAINT [PK_Departments] PRIMARY KEY CLUSTERED ([DepartmentID])
)
GO
CREATE TABLE [dbo].[Projects]([ProjectID] [int] NOT NULL PRIMARY KEY, [Title] [nvarchar](200) NOT NULL, [Status] [varchar](10) NOT NULL CHECK ([Status] IN ('open','closed')))
GO
CREATE TABLE [dbo].[EmployeeProjects](
	[EmployeeID] [int] NOT NULL,
	[ProjectID] [int] NOT NULL,
 CONSTRAINT [PK_EmployeeProjects] PRIMARY KEY CLUSTERED ([EmployeeID], [ProjectID])
)
GO
ALTER TABLE [dbo].[Employees] ADD DEFAULT ((1)) FOR [Active]
GO
ALTER TABLE [dbo].[Employees] WITH CHECK ADD CONSTRAINT [FK_Employees_Departments] FOREIGN KEY([DepartmentID]) REFERENCES [dbo].[Departments] ([DepartmentID])
GO
ALTER TABLE [dbo].[Employees] WITH CHECK ADD CONSTRAINT [FK_Employees_Manager] FOREIGN KEY([ManagerID]) REFERENCES [dbo].[Employees] ([EmployeeID])
GO
ALTER TABLE [dbo].[EmployeeProjects] WITH CHECK ADD CONSTRAINT [FK_EP_E] FOREIGN KEY([EmployeeID]) REFERENCES [dbo].[Employees] ([EmployeeID])
GO
ALTER TABLE [dbo].[EmployeeProjects] WITH CHECK ADD CONSTRAINT [FK_EP_P] FOREIGN KEY([ProjectID]) REFERENCES [dbo].[Projects] ([ProjectID])
GO
EXEC sys.sp_addextendedproperty @name=N'MS_Description', @value=N'Personnel de la société' , @level0type=N'SCHEMA',@level0name=N'dbo', @level1type=N'TABLE',@level1name=N'Employees'
GO
